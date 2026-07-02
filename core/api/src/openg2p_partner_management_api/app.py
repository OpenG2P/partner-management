# ruff: noqa: E402
import asyncio
import logging

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer as BaseInitializer

from .controllers import (
    AdminPartnerController,
    AdminRequestController,
    KeyFetchController,
)
from .migrations import migrate_all
from .services import KeyService, PartnerService, RequestService

_logger = logging.getLogger(_config.logging_default_logger_name)


class Initializer(BaseInitializer):
    """Combined initializer: registers every controller in one app.

    Used for local all-in-one dev and the test suite. Production deploys the two
    split entrypoints instead — see ``staff_portal_main`` and ``partner_main``.
    """

    def initialize(self, **kwargs):
        super().initialize()
        KeyService()
        PartnerService()
        RequestService()
        AdminRequestController().post_init()
        AdminPartnerController().post_init()
        KeyFetchController().post_init()

    def migrate_database(self, args):
        super().migrate_database(args)
        asyncio.run(migrate_all())
