from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .key import KeyInput


class OnboardingRequestCreate(BaseModel):
    """Onboard a new partner and its initial public key(s)."""

    partner_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    org_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(
        default=None, description="Free-text description of the onboarding request"
    )
    jwks_url: Optional[str] = Field(default=None, max_length=1024)
    # Keys pasted directly. May be empty if import_from_jwks_url is set.
    keys: List[KeyInput] = Field(default_factory=list)
    # When true and jwks_url is set, keys are fetched from it and stored.
    import_from_jwks_url: bool = False


class KeyUpdateRequestCreate(BaseModel):
    """File a key rotation / update request for an existing partner."""

    partner_id: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(
        default=None, description="Why the keys are changing (e.g. scheduled rotation)"
    )
    keys: List[KeyInput] = Field(default_factory=list)
    jwks_url: Optional[str] = Field(default=None, max_length=1024)
    import_from_jwks_url: bool = False
    # kids of existing keys to revoke when this request is approved.
    revoke_kids: List[str] = Field(default_factory=list)


class RequestReview(BaseModel):
    notes: Optional[str] = None


class ProposedKey(BaseModel):
    kid: str
    algorithm: str
    key_fingerprint: Optional[str] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None


class PartnerRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_type: str  # onboarding | key_update
    partner_id: str
    name: Optional[str] = None
    org_name: Optional[str] = None
    description: Optional[str] = None
    jwks_url: Optional[str] = None
    proposed_keys: list = Field(default_factory=list)
    revoke_kids: list = Field(default_factory=list)
    status: str  # created | approved | rejected
    submitted_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PartnerRequestListResponse(BaseModel):
    count: int
    requests: list[PartnerRequestResponse]
