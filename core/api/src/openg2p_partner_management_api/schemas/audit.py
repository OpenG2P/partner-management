from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    partner_id: str
    request_id: Optional[str] = None
    details: dict = {}


class AuditEventListResponse(BaseModel):
    count: int
    events: list[AuditEventResponse]
