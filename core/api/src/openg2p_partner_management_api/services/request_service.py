import logging
from datetime import datetime

from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.service import BaseService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import Settings
from ..errors import (
    InvalidKeyError,
    PartnerExistsError,
    PartnerNotFoundError,
    RequestNotFoundError,
    RequestNotOpenError,
)
from ..models import (
    KeyStatus,
    Partner,
    PartnerKey,
    PartnerRequest,
    PartnerStatus,
    RequestStatus,
    RequestType,
)
from .key_service import KeyService
from .partner_service import PartnerService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


def _sm():
    return async_sessionmaker(dbengine.get(), expire_on_commit=False)


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class RequestService(BaseService):
    """Creates onboarding / key-update requests and applies them on approval.

    Key material is normalised and validated up front (at request creation), so
    approval is a cheap, deterministic apply. In v1 the admin both files and
    approves; the same apply path is reused for a future AWE webhook.
    """

    keys = KeyService.get_cached_component()
    partners = PartnerService.get_cached_component()

    # --- creation ------------------------------------------------------------

    async def _collect_and_normalize(self, key_inputs, jwks_url, do_import) -> list[dict]:
        normalized: list[dict] = []
        for k in key_inputs:
            nk = self.keys.normalize(
                public_key=k.public_key, jwk=k.jwk, kid=k.kid, algorithm=k.algorithm
            )
            normalized.append(nk.as_dict(k.not_before, k.not_after))

        if do_import:
            if not jwks_url:
                raise InvalidKeyError("import_from_jwks_url is set but jwks_url is empty.")
            for fetched in await self.keys.fetch_jwks_keys(jwks_url):
                nk = self.keys.normalize(jwk=fetched["jwk"], kid=fetched.get("kid"))
                normalized.append(nk.as_dict())

        # De-duplicate by fingerprint (last wins, keeping validity from that entry).
        deduped: dict[str, dict] = {}
        for n in normalized:
            deduped[n["key_fingerprint"]] = n
        return list(deduped.values())

    async def create_onboarding(self, data, actor: str = None) -> PartnerRequest:
        if await self.partners.get_partner(data.partner_id):
            raise PartnerExistsError(data.partner_id)

        proposed = await self._collect_and_normalize(
            data.keys, data.jwks_url, data.import_from_jwks_url
        )
        if not proposed:
            raise InvalidKeyError("At least one public key is required to onboard a partner.")

        async with _sm()() as session:
            session.add(
                Partner(
                    partner_id=data.partner_id,
                    name=data.name,
                    org_name=data.org_name,
                    description=data.description,
                    jwks_url=data.jwks_url,
                    status=PartnerStatus.created.value,
                    created_by=actor,
                )
            )
            req = PartnerRequest(
                request_type=RequestType.onboarding.value,
                partner_id=data.partner_id,
                name=data.name,
                org_name=data.org_name,
                description=data.description,
                jwks_url=data.jwks_url,
                proposed_keys=proposed,
                revoke_kids=[],
                status=RequestStatus.created.value,
                submitted_by=actor,
            )
            session.add(req)
            await session.commit()
            await session.refresh(req)
            return req

    async def create_key_update(self, data, actor: str = None) -> PartnerRequest:
        partner = await self.partners.get_partner(data.partner_id)
        if not partner:
            raise PartnerNotFoundError(data.partner_id)

        proposed = await self._collect_and_normalize(
            data.keys, data.jwks_url, data.import_from_jwks_url
        )
        if not proposed and not data.revoke_kids:
            raise InvalidKeyError("Provide at least one key to add or one kid to revoke.")

        async with _sm()() as session:
            req = PartnerRequest(
                request_type=RequestType.key_update.value,
                partner_id=data.partner_id,
                description=data.description,
                jwks_url=data.jwks_url,
                proposed_keys=proposed,
                revoke_kids=list(data.revoke_kids or []),
                status=RequestStatus.created.value,
                submitted_by=actor,
            )
            session.add(req)
            await session.commit()
            await session.refresh(req)
            return req

    # --- reads ---------------------------------------------------------------

    async def get_request(self, request_id: str) -> PartnerRequest:
        async with _sm()() as session:
            req = await session.get(PartnerRequest, request_id)
            if not req:
                raise RequestNotFoundError(request_id)
            return req

    async def list_requests(self, status: str = None, partner_id: str = None) -> list[PartnerRequest]:
        async with _sm()() as session:
            stmt = select(PartnerRequest).order_by(PartnerRequest.created_at.desc())
            if status:
                stmt = stmt.where(PartnerRequest.status == status)
            if partner_id:
                stmt = stmt.where(PartnerRequest.partner_id == partner_id)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    # --- decisions -----------------------------------------------------------

    async def approve(self, request_id: str, actor: str = None, notes: str = None) -> PartnerRequest:
        async with _sm()() as session:
            req = await session.get(PartnerRequest, request_id)
            if not req:
                raise RequestNotFoundError(request_id)
            if req.status != RequestStatus.created.value:
                raise RequestNotOpenError(
                    f"Request is '{req.status}', only 'created' requests can be approved."
                )

            res = await session.execute(
                select(Partner).where(Partner.partner_id == req.partner_id)
            )
            partner = res.scalars().first()
            if not partner:
                raise PartnerNotFoundError(req.partner_id)

            # Onboarding flips the partner active; key_update leaves status as-is.
            if req.request_type == RequestType.onboarding.value:
                partner.status = PartnerStatus.active.value
                partner.approved_by = actor

            for pk in req.proposed_keys or []:
                await self._upsert_key(session, req.partner_id, pk)

            for kid in req.revoke_kids or []:
                await self._revoke_key(session, req.partner_id, kid)

            req.status = RequestStatus.approved.value
            req.reviewed_by = actor
            req.review_notes = notes
            await session.commit()
            await session.refresh(req)
            return req

    async def reject(self, request_id: str, actor: str = None, notes: str = None) -> PartnerRequest:
        async with _sm()() as session:
            req = await session.get(PartnerRequest, request_id)
            if not req:
                raise RequestNotFoundError(request_id)
            if req.status != RequestStatus.created.value:
                raise RequestNotOpenError(
                    f"Request is '{req.status}', only 'created' requests can be rejected."
                )
            # A rejected onboarding leaves the partner in 'created' (never served);
            # the admin can disable or resubmit. No keys were materialised.
            req.status = RequestStatus.rejected.value
            req.reviewed_by = actor
            req.review_notes = notes
            await session.commit()
            await session.refresh(req)
            return req

    # --- apply helpers -------------------------------------------------------

    async def _upsert_key(self, session, partner_id: str, pk: dict):
        res = await session.execute(
            select(PartnerKey).where(
                PartnerKey.partner_id == partner_id, PartnerKey.kid == pk["kid"]
            )
        )
        existing = res.scalars().first()
        if existing:
            existing.algorithm = pk["algorithm"]
            existing.public_key = pk["public_key"]
            existing.key_fingerprint = pk.get("key_fingerprint")
            existing.status = KeyStatus.active.value
            existing.not_before = _parse_dt(pk.get("not_before"))
            existing.not_after = _parse_dt(pk.get("not_after"))
        else:
            session.add(
                PartnerKey(
                    partner_id=partner_id,
                    kid=pk["kid"],
                    algorithm=pk["algorithm"],
                    public_key=pk["public_key"],
                    key_fingerprint=pk.get("key_fingerprint"),
                    status=KeyStatus.active.value,
                    not_before=_parse_dt(pk.get("not_before")),
                    not_after=_parse_dt(pk.get("not_after")),
                )
            )

    async def _revoke_key(self, session, partner_id: str, kid: str):
        res = await session.execute(
            select(PartnerKey).where(
                PartnerKey.partner_id == partner_id, PartnerKey.kid == kid
            )
        )
        key = res.scalars().first()
        if key:
            key.status = KeyStatus.revoked.value
