import logging

from .config import Settings
from .models import AuditEvent, Partner, PartnerKey, PartnerRequest

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


async def migrate_all():
    """Create all Partner Management tables (idempotent).

    Shared by both service entrypoints (staff-portal-api and partner-api) since
    they run against the same database.
    """
    _logger.info("Migrating Partner Management database")
    await Partner.create_migrate()
    await PartnerKey.create_migrate()
    await PartnerRequest.create_migrate()
    await AuditEvent.create_migrate()
