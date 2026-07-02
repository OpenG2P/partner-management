# ruff: noqa: E402
import asyncio
import logging

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer as BaseInitializer

from .controllers import AdminPartnerController, AdminRequestController
from .migrations import migrate_all
from .services import KeyService, PartnerService, RequestService

_logger = logging.getLogger(_config.logging_default_logger_name)


class Initializer(BaseInitializer):
    """staff-portal-api: the staff/admin-facing service.

    Serves onboarding, key-rotation and partner-management endpoints, all guarded
    by a Keycloak staff-realm JWT (see auth.PartnerManagerAuth). Backs the admin
    UI. Does not expose the public key-fetch routes.
    """

    def initialize(self, **kwargs):
        super().initialize()
        KeyService()
        PartnerService()
        RequestService()
        AdminRequestController().post_init()
        AdminPartnerController().post_init()

    def migrate_database(self, args):
        super().migrate_database(args)
        asyncio.run(migrate_all())
