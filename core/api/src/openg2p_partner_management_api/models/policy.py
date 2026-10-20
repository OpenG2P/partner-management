from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModelWithId

# JSONB on PostgreSQL (production), plain JSON elsewhere (e.g. SQLite in tests).
_JSONList = JSON().with_variant(JSONB(), "postgresql")


class PolicyStatus(str, Enum):
    # pending: proposed by an open request, not served.
    # active: served by the policy-fetch API (one per partner + data controller).
    # superseded: replaced by a newer approved version.
    # rejected: its request was rejected.
    # revoked: withdrawn by an approved policy request; nothing replaces it.
    pending = "pending"
    active = "active"
    superseded = "superseded"
    rejected = "rejected"
    revoked = "revoked"


class FetchType(str, Enum):
    oneshot = "oneshot"
    periodic = "periodic"


class PartnerPolicy(BaseModelWithId):
    """What a partner may access, versioned per (partner, data controller).

    ``data_controller`` set = a scope policy for one registry
    (``allowed_data_scopes``); null = a use-case policy for an exchange
    (``allowed_use_cases``). Changes are made only through partner requests:
    each request creates ``pending`` versions that approval turns ``active``
    (the previous active version becomes ``superseded``). Rows are never deleted.
    """

    __tablename__ = "pm_partner_policies"

    partner_id: Mapped[str] = mapped_column(String(255), index=True)
    # Registry's controller id (e.g. "farmer_registry"); null = use-case policy.
    data_controller: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default=PolicyStatus.pending.value, index=True
    )

    allowed_data_scopes: Mapped[list] = mapped_column(_JSONList, default=list)
    allowed_use_cases: Mapped[list] = mapped_column(_JSONList, default=list)
    allowed_purposes: Mapped[list] = mapped_column(_JSONList, default=list)
    allowed_subject_id_types: Mapped[list] = mapped_column(_JSONList, default=list)
    allowed_signing_algs: Mapped[list] = mapped_column(_JSONList, default=list)
    # ISO-8601 durations (e.g. P1Y); null = no limit.
    max_validity_duration: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fetch_type: Mapped[str] = mapped_column(String(20), default=FetchType.oneshot.value)
    max_fetch_frequency: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    data_life: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # The partner request that proposed this version.
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    # Approval time; null until approved.
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
