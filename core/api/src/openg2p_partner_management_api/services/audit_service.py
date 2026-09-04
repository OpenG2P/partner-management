import logging

from openg2p_fastapi_common.context import get_async_session_maker
from openg2p_fastapi_common.service import BaseService
from sqlalchemy import select

from ..config import Settings
from ..models import AuditAction, AuditEvent

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class AuditService(BaseService):
    """Writes the append-only local audit ledger and reads it back per partner.

    ``record`` adds a row to the CALLER'S session (no commit), so the audit entry
    lands in the same transaction as the change it describes — atomic, never lost.
    """

    def record(
        self,
        session,
        *,
        action: AuditAction,
        entity_type: str,
        partner_id: str,
        entity_id: str = None,
        request_id: str = None,
        actor: dict = None,
        details: dict = None,
    ):
        actor = actor or {}
        session.add(
            AuditEvent(
                action=action.value if isinstance(action, AuditAction) else str(action),
                entity_type=entity_type,
                entity_id=entity_id,
                partner_id=partner_id,
                request_id=request_id,
                actor_id=actor.get("id"),
                actor_name=actor.get("name"),
                details=details or {},
            )
        )

    async def list_for_partner(self, partner_id: str) -> list[AuditEvent]:
        session_maker = get_async_session_maker()
        async with session_maker() as session:
            res = await session.execute(
                select(AuditEvent)
                .where(AuditEvent.partner_id == partner_id)
                .order_by(AuditEvent.created_at.desc())
            )
            return list(res.scalars().all())
