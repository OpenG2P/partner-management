from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    partner_id: str
    name: str
    org_name: Optional[str] = None
    description: Optional[str] = None
    jwks_url: Optional[str] = None
    status: str  # created | active | disabled
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PartnerListResponse(BaseModel):
    count: int
    partners: list[PartnerResponse]


class PartnerActionResponse(BaseModel):
    """Returned by disable/enable and other partner state transitions."""

    partner_id: str
    status: str
    message: str = Field(default="")
