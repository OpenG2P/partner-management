from enum import Enum
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModelWithId

# JSONB on PostgreSQL (production), plain JSON elsewhere (e.g. SQLite in tests).
_JSONList = JSON().with_variant(JSONB(), "postgresql")


class RequestType(str, Enum):
    onboarding = "onboarding"
    key_update = "key_update"  # key rotation / addition / revocation


class RequestStatus(str, Enum):
    created = "created"
    approved = "approved"
    rejected = "rejected"


class PartnerRequest(BaseModelWithId):
    """An admin-facing workflow record for onboarding or key rotation.

    The submitted key material is normalised (to canonical PEM) and validated at
    creation time and stashed in ``proposed_keys`` so approval is a cheap apply.
    In v1 the admin both files and approves; ``awe_request_id`` is reserved for a
    later Approval Workflow Engine integration (mirrors consent-manager).
    """

    __tablename__ = "pm_partner_requests"

    request_type: Mapped[str] = mapped_column(String(20), index=True)
    partner_id: Mapped[str] = mapped_column(String(255), index=True)

    # Snapshot of partner attributes proposed by an onboarding request.
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    org_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jwks_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Normalised keys to activate on approval: list of
    # {kid, algorithm, public_key(PEM), key_fingerprint, not_before, not_after}.
    proposed_keys: Mapped[list] = mapped_column(_JSONList, default=list)
    # kids to revoke on approval (key rotation retirement).
    revoke_kids: Mapped[list] = mapped_column(_JSONList, default=list)

    status: Mapped[str] = mapped_column(
        String(20), default=RequestStatus.created.value, index=True
    )
    submitted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reserved for future AWE integration (currently always null in v1).
    awe_request_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
