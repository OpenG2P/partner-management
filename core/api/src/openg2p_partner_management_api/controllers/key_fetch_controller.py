import logging

from fastapi import Response
from openg2p_fastapi_common.controller import BaseController

from ..config import Settings
from ..errors import KeysNotAvailableError
from ..schemas import PublicKeyListResponse, PublicKeyResponse
from ..services import KeyService, PartnerService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class KeyFetchController(BaseController):
    """Unauthenticated key-fetch APIs used by other OpenG2P modules.

    No caller signature is required: the responses contain only public key
    material, and the routes are exposed on the cluster-internal gateway. The
    API is fail-closed — an unknown partner, a non-active partner, or one with no
    currently-valid keys all return the same 404 "not available", so callers
    cannot distinguish those states or enumerate partners.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.partners = PartnerService.get_component()
        self.keys = KeyService.get_component()
        self.router.tags += ["Public: Key Fetch"]

        self.router.add_api_route(
            "/keys/{partner_id}",
            self.get_keys,
            methods=["GET"],
            responses={200: {"model": PublicKeyListResponse}},
        )
        self.router.add_api_route(
            "/keys/{partner_id}/jwks.json",
            self.get_jwks,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/keys/{partner_id}/{kid}",
            self.get_key,
            methods=["GET"],
            responses={200: {"model": PublicKeyResponse}},
        )

    def _cache(self, response: Response):
        response.headers["Cache-Control"] = f"public, max-age={_config.key_fetch_cache_max_age}"

    async def get_keys(self, partner_id: str, response: Response) -> PublicKeyListResponse:
        keys = await self.partners.get_servable_keys(partner_id)
        if not keys:
            raise KeysNotAvailableError(partner_id)
        self._cache(response)
        return PublicKeyListResponse(
            partner_id=partner_id,
            keys=[PublicKeyResponse(**k) for k in keys],
        )

    async def get_key(self, partner_id: str, kid: str, response: Response) -> PublicKeyResponse:
        keys = await self.partners.get_servable_keys(partner_id)
        match = next((k for k in (keys or []) if k["kid"] == kid), None)
        if not match:
            raise KeysNotAvailableError(partner_id)
        self._cache(response)
        return PublicKeyResponse(**match)

    async def get_jwks(self, partner_id: str, response: Response) -> dict:
        keys = await self.partners.get_servable_keys(partner_id)
        if not keys:
            raise KeysNotAvailableError(partner_id)
        self._cache(response)
        return self.keys.to_jwks(keys)
