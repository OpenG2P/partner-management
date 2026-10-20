from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import IDENTIFIER_PATTERN
from .key import KeyInput, blank_to_none
from .policy import PolicyInput, check_distinct_controllers


def _check_jwks_url(value):
    value = blank_to_none(value)
    if value is None:
        return None
    value = value.strip()
    if not value.lower().startswith(("https://", "http://")):
        raise ValueError("jwks_url must be an http(s) URL.")
    return value


class OnboardingRequestCreate(BaseModel):
    """Onboard a new partner and its initial public key(s)."""

    partner_id: str = Field(..., min_length=1, max_length=255, pattern=IDENTIFIER_PATTERN)
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
    # Optional access policies, activated (version 1) when the partner is approved.
    policies: List[PolicyInput] = Field(default_factory=list)

    _jwks_url = field_validator("jwks_url", mode="before")(_check_jwks_url)
    _policies = field_validator("policies")(check_distinct_controllers)


class KeyUpdateRequestCreate(BaseModel):
    """File a key rotation / update request for an existing partner."""

    partner_id: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(
        default=None, description="Why the keys are changing (e.g. scheduled rotation)"
    )
    keys: List[KeyInput] = Field(default_factory=list)
    jwks_url: Optional[str] = Field(default=None, max_length=1024)
    import_from_jwks_url: bool = False
    # kids of existing keys to revoke when this request is approved. Each must
    # be a current (non-revoked) key of the partner — checked in RequestService.
    revoke_kids: List[str] = Field(default_factory=list)

    _jwks_url = field_validator("jwks_url", mode="before")(_check_jwks_url)


class PolicyRequestCreate(BaseModel):
    """Change an existing partner's access policies.

    Each policy becomes a new active version on approval (the previous one is
    superseded); each data controller in ``revoke_data_controllers`` has its
    active policy revoked (null = the use-case policy).
    """

    partner_id: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(
        default=None, description="Why the policy is changing"
    )
    policies: List[PolicyInput] = Field(default_factory=list)
    revoke_data_controllers: List[Optional[str]] = Field(
        default_factory=list, examples=[["farmer_registry", None]]
    )

    _policies = field_validator("policies")(check_distinct_controllers)

    @field_validator("revoke_data_controllers", mode="before")
    @classmethod
    def _revoke_blank_is_use_case(cls, values):
        # "" is how a form sends the use-case policy; store it as null. Deduped.
        out = []
        for v in values or []:
            v = blank_to_none(v)
            v = v.strip() if isinstance(v, str) else v
            if v not in out:
                out.append(v)
        return out


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
    request_type: str  # onboarding | key_update | policy
    partner_id: str
    name: Optional[str] = None
    org_name: Optional[str] = None
    description: Optional[str] = None
    jwks_url: Optional[str] = None
    proposed_keys: list = Field(default_factory=list)
    revoke_kids: list = Field(default_factory=list)
    proposed_policies: list = Field(default_factory=list)
    revoke_data_controllers: list = Field(default_factory=list)
    status: str  # created | approved | rejected
    submitted_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PartnerRequestListResponse(BaseModel):
    count: int
    requests: list[PartnerRequestResponse]
