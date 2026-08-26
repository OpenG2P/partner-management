import logging
from typing import Annotated, Optional

from fastapi import Depends
from openg2p_fastapi_common.controller import BaseController

from ..auth import AuthCredentials, PartnerManagerAuth
from ..config import Settings
from ..schemas import (
    KeyUpdateRequestCreate,
    OnboardingRequestCreate,
    PartnerRequestListResponse,
    PartnerRequestResponse,
    RequestReview,
)
from ..services import RequestService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)

_admin_auth = PartnerManagerAuth()


class AdminRequestController(BaseController):
    """Staff-realm APIs to file and decide onboarding / key-rotation requests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requests = RequestService.get_component()
        self.router.tags += ["Admin: Partner Requests"]

        self.router.add_api_route(
            "/partners/requests/onboarding",
            self.create_onboarding,
            methods=["POST"],
            responses={200: {"model": PartnerRequestResponse}},
        )
        self.router.add_api_route(
            "/partners/requests/key-update",
            self.create_key_update,
            methods=["POST"],
            responses={200: {"model": PartnerRequestResponse}},
        )
        self.router.add_api_route(
            "/partners/requests",
            self.list_requests,
            methods=["GET"],
            responses={200: {"model": PartnerRequestListResponse}},
        )
        self.router.add_api_route(
            "/partners/requests/{request_id}",
            self.get_request,
            methods=["GET"],
            responses={200: {"model": PartnerRequestResponse}},
        )
        self.router.add_api_route(
            "/partners/requests/{request_id}/approve",
            self.approve_request,
            methods=["POST"],
            responses={200: {"model": PartnerRequestResponse}},
        )
        self.router.add_api_route(
            "/partners/requests/{request_id}/reject",
            self.reject_request,
            methods=["POST"],
            responses={200: {"model": PartnerRequestResponse}},
        )

    async def create_onboarding(
        self,
        data: OnboardingRequestCreate,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
    ) -> PartnerRequestResponse:
        req = await self.requests.create_onboarding(data, actor=PartnerManagerAuth.actor_info(auth))
        return PartnerRequestResponse.model_validate(req)

    async def create_key_update(
        self,
        data: KeyUpdateRequestCreate,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
    ) -> PartnerRequestResponse:
        req = await self.requests.create_key_update(data, actor=PartnerManagerAuth.actor_info(auth))
        return PartnerRequestResponse.model_validate(req)

    async def list_requests(
        self,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
        status: Optional[str] = None,
        partner_id: Optional[str] = None,
    ) -> PartnerRequestListResponse:
        rows = await self.requests.list_requests(status=status, partner_id=partner_id)
        return PartnerRequestListResponse(
            count=len(rows),
            requests=[PartnerRequestResponse.model_validate(r) for r in rows],
        )

    async def get_request(
        self,
        request_id: str,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
    ) -> PartnerRequestResponse:
        req = await self.requests.get_request(request_id)
        return PartnerRequestResponse.model_validate(req)

    async def approve_request(
        self,
        request_id: str,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
        review: RequestReview = RequestReview(),
    ) -> PartnerRequestResponse:
        req = await self.requests.approve(
            request_id, actor=PartnerManagerAuth.actor_info(auth), notes=review.notes
        )
        return PartnerRequestResponse.model_validate(req)

    async def reject_request(
        self,
        request_id: str,
        auth: Annotated[AuthCredentials, Depends(_admin_auth)],
        review: RequestReview = RequestReview(),
    ) -> PartnerRequestResponse:
        req = await self.requests.reject(
            request_id, actor=PartnerManagerAuth.actor_info(auth), notes=review.notes
        )
        return PartnerRequestResponse.model_validate(req)
