import logging
from datetime import datetime, timezone
from typing import Optional

from openg2p_fastapi_common.service import BaseService
from sqlalchemy import func, select

from ..config import Settings
from ..errors import InvalidPolicyError, PolicyPendingError
from ..models import (
    AuditAction,
    Partner,
    PartnerPolicy,
    PartnerRequest,
    PartnerStatus,
    PolicyStatus,
    RequestStatus,
)
from .audit_service import AuditService
from .partner_service import session_maker

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _controller_is(data_controller: Optional[str]):
    """WHERE clause for one data controller; None = the use-case policy."""
    if data_controller is None:
        return PartnerPolicy.data_controller.is_(None)
    return PartnerPolicy.data_controller == data_controller


def _label(data_controller: Optional[str]) -> str:
    return data_controller or "(use cases)"


class PolicyService(BaseService):
    """Partner access policies: versioned per (partner, data controller).

    Writes happen only inside a partner request's transaction (RequestService
    passes its session): a request adds ``pending`` versions, approval activates
    them (superseding the previous active one) and applies revocations,
    rejection marks them ``rejected``. Reads back the policy-fetch API, which is
    fail-closed like key fetch.
    """

    audit = AuditService.get_cached_component()

    # --- request side (caller's session, no commit) --------------------------

    async def check_proposal(
        self, session, partner_id: str, policies: list, revoke: list
    ) -> None:
        """Reject a proposal that clashes with an open one or revokes nothing.

        At most one pending change per (partner, data controller): a pending
        version or an open request revoking it both count.
        """
        proposed = [p.data_controller for p in policies]
        if not proposed and not revoke:
            raise InvalidPolicyError("Provide at least one policy or one policy to revoke.")
        both = [c for c in revoke if c in proposed]
        if both:
            raise InvalidPolicyError(
                f"Cannot both change and revoke the policy for {[_label(c) for c in both]}."
            )

        res = await session.execute(
            select(PartnerPolicy).where(
                PartnerPolicy.partner_id == partner_id,
                PartnerPolicy.status == PolicyStatus.pending.value,
            )
        )
        busy = {p.data_controller: p.request_id for p in res.scalars().all()}
        res = await session.execute(
            select(PartnerRequest).where(
                PartnerRequest.partner_id == partner_id,
                PartnerRequest.status == RequestStatus.created.value,
            )
        )
        for open_req in res.scalars().all():
            for c in open_req.revoke_data_controllers or []:
                busy.setdefault(c, open_req.id)
        clash = [c for c in proposed + revoke if c in busy]
        if clash:
            raise PolicyPendingError(
                "A policy change is already pending for "
                + ", ".join(f"{_label(c)} (request {busy[c]})" for c in clash)
                + ". Approve or reject it first."
            )

        if revoke:
            active = await self._active_controllers(session, partner_id)
            missing = [c for c in revoke if c not in active]
            if missing:
                raise InvalidPolicyError(
                    f"Cannot revoke {[_label(c) for c in missing]}: no active policy. "
                    f"Active: {sorted(_label(c) for c in active)}."
                )

    async def add_pending(
        self, session, partner_id: str, policies: list, request_id: str, actor: dict = None
    ) -> list[PartnerPolicy]:
        rows = []
        for p in policies:
            res = await session.execute(
                select(func.max(PartnerPolicy.version)).where(
                    PartnerPolicy.partner_id == partner_id, _controller_is(p.data_controller)
                )
            )
            version = (res.scalar() or 0) + 1
            row = PartnerPolicy(
                partner_id=partner_id,
                version=version,
                status=PolicyStatus.pending.value,
                request_id=request_id,
                created_by=(actor or {}).get("name"),
                **p.model_dump(),
            )
            session.add(row)
            rows.append(row)
            self.audit.record(
                session,
                action=AuditAction.policy_requested,
                entity_type="partner_policy",
                entity_id=row.id,
                partner_id=partner_id,
                request_id=request_id,
                actor=actor,
                details={"data_controller": p.data_controller, "version": version},
            )
        return rows

    async def apply_approval(self, session, req: PartnerRequest, actor: dict = None) -> dict:
        """Activate the request's pending versions and apply its revocations."""
        now = _utcnow()
        actor_name = (actor or {}).get("name")
        activated, revoked = [], []

        for row in await self._request_rows(session, req.id):
            for old in await self._active(session, req.partner_id, row.data_controller):
                old.status = PolicyStatus.superseded.value
            row.status = PolicyStatus.active.value
            row.effective_from = now
            row.approved_by = actor_name
            activated.append({"data_controller": row.data_controller, "version": row.version})
            self.audit.record(
                session,
                action=AuditAction.policy_approved,
                entity_type="partner_policy",
                entity_id=row.id,
                partner_id=req.partner_id,
                request_id=req.id,
                actor=actor,
                details={"data_controller": row.data_controller, "version": row.version},
            )

        for controller in req.revoke_data_controllers or []:
            for old in await self._active(session, req.partner_id, controller):
                old.status = PolicyStatus.revoked.value
                revoked.append({"data_controller": controller, "version": old.version})
                self.audit.record(
                    session,
                    action=AuditAction.policy_revoked,
                    entity_type="partner_policy",
                    entity_id=old.id,
                    partner_id=req.partner_id,
                    request_id=req.id,
                    actor=actor,
                    details={"data_controller": controller, "version": old.version},
                )
        return {"policies_activated": activated, "policies_revoked": revoked}

    async def apply_rejection(self, session, req: PartnerRequest, actor: dict = None) -> None:
        for row in await self._request_rows(session, req.id):
            row.status = PolicyStatus.rejected.value
            self.audit.record(
                session,
                action=AuditAction.policy_rejected,
                entity_type="partner_policy",
                entity_id=row.id,
                partner_id=req.partner_id,
                request_id=req.id,
                actor=actor,
                details={"data_controller": row.data_controller, "version": row.version},
            )

    async def _request_rows(self, session, request_id: str) -> list[PartnerPolicy]:
        res = await session.execute(
            select(PartnerPolicy).where(
                PartnerPolicy.request_id == request_id,
                PartnerPolicy.status == PolicyStatus.pending.value,
            )
        )
        return list(res.scalars().all())

    async def _active(self, session, partner_id: str, data_controller) -> list[PartnerPolicy]:
        res = await session.execute(
            select(PartnerPolicy).where(
                PartnerPolicy.partner_id == partner_id,
                _controller_is(data_controller),
                PartnerPolicy.status == PolicyStatus.active.value,
            )
        )
        return list(res.scalars().all())

    async def _active_controllers(self, session, partner_id: str) -> set:
        res = await session.execute(
            select(PartnerPolicy.data_controller).where(
                PartnerPolicy.partner_id == partner_id,
                PartnerPolicy.status == PolicyStatus.active.value,
            )
        )
        return set(res.scalars().all())

    # --- reads ---------------------------------------------------------------

    async def list_for_partner(self, partner_id: str, all_versions: bool = False) -> list[PartnerPolicy]:
        """Staff view: active policies, or every version (newest first)."""
        async with session_maker()() as session:
            stmt = select(PartnerPolicy).where(PartnerPolicy.partner_id == partner_id)
            if not all_versions:
                stmt = stmt.where(PartnerPolicy.status == PolicyStatus.active.value)
            stmt = stmt.order_by(PartnerPolicy.data_controller, PartnerPolicy.version.desc())
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_servable_policies(
        self, partner_id: str, data_controller: Optional[str] = None
    ) -> list[PartnerPolicy] | None:
        """Active policies of an ACTIVE partner, else None (fail-closed).

        ``data_controller``: None = all; "" = the use-case policy; else that
        controller's policy. An unknown / non-active partner and one with no
        matching active policy all return None.
        """
        async with session_maker()() as session:
            res = await session.execute(
                select(Partner).where(Partner.partner_id == partner_id)
            )
            partner = res.scalars().first()
            if not partner or partner.status != PartnerStatus.active.value:
                return None
            stmt = select(PartnerPolicy).where(
                PartnerPolicy.partner_id == partner_id,
                PartnerPolicy.status == PolicyStatus.active.value,
            )
            if data_controller is not None:
                stmt = stmt.where(_controller_is(data_controller.strip() or None))
            res = await session.execute(stmt.order_by(PartnerPolicy.data_controller))
            return list(res.scalars().all()) or None

    async def list_servable(
        self, use_case: Optional[str] = None, data_controller: Optional[str] = None
    ) -> list[PartnerPolicy]:
        """Active policies of active partners, optionally filtered (for listings)."""
        async with session_maker()() as session:
            stmt = (
                select(PartnerPolicy)
                .join(Partner, Partner.partner_id == PartnerPolicy.partner_id)
                .where(
                    Partner.status == PartnerStatus.active.value,
                    PartnerPolicy.status == PolicyStatus.active.value,
                )
            )
            if data_controller is not None:
                stmt = stmt.where(_controller_is(data_controller.strip() or None))
            stmt = stmt.order_by(PartnerPolicy.partner_id, PartnerPolicy.data_controller)
            rows = list((await session.execute(stmt)).scalars().all())
        if use_case:
            # JSON containment differs between PostgreSQL and SQLite; filter here.
            rows = [r for r in rows if use_case in (r.allowed_use_cases or [])]
        return rows
