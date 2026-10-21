import logging

from openg2p_fastapi_common.context import dbengine
from sqlalchemy import text

from .config import Settings
from .models import AuditEvent, Partner, PartnerKey, PartnerPolicy, PartnerRequest

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
    await _add_missing_columns()
    await PartnerPolicy.create_migrate()
    await AuditEvent.create_migrate()


# Columns added after a table first shipped: create_all() does not add columns
# to an existing table. PostgreSQL only (tests create fresh SQLite tables).
_ADDED_COLUMNS = [
    ("pm_partner_requests", "warnings", "JSONB DEFAULT '[]'::jsonb"),
]


async def _add_missing_columns():
    engine = dbengine.get()
    if engine.dialect.name != "postgresql":
        return
    async with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))
