from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModelWithId


class PartnerStatus(str, Enum):
    # created: onboarded, awaiting admin approval. Keys are NOT served.
    # active: approved; active keys are served by the fetch API.
    # disabled: turned off; the fetch API returns "not available".
    created = "created"
    active = "active"
    disabled = "disabled"


class KeyStatus(str, Enum):
    # pending: submitted, awaiting approval of its parent request.
    # active: served by the fetch API (subject to not_before/not_after).
    # revoked: never served; retained for audit.
    pending = "pending"
    active = "active"
    revoked = "revoked"


class Partner(BaseModelWithId):
    """A third party whose signatures other OpenG2P modules need to verify."""

    __tablename__ = "pm_partners"

    # Admin-supplied, stable business identifier callers use to fetch keys
    # (e.g. "PARTNER_G2P_BRIDGE" or an audience/mnemonic). Unique.
    partner_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    org_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Optional well-known JWKS endpoint the admin may import keys from.
    jwks_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=PartnerStatus.created.value, index=True
    )
    # Audit: subject of the staff-realm token that created / approved the partner.
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class PartnerKey(BaseModelWithId):
    """One public key belonging to a partner, addressed by (partner_id, kid).

    Multiple ``active`` keys per partner are allowed so rotation is an overlap
    operation: activate the new key, then revoke the old one after callers have
    picked it up (bounded by the fetch cache TTL).
    """

    __tablename__ = "pm_partner_keys"
    __table_args__ = (
        UniqueConstraint("partner_id", "kid", name="uq_pm_partner_kid"),
    )

    partner_id: Mapped[str] = mapped_column(String(255), index=True)
    kid: Mapped[str] = mapped_column(String(255), index=True)
    algorithm: Mapped[str] = mapped_column(String(20))  # RS256 | ES256 | EdDSA
    # Canonical PEM (SubjectPublicKeyInfo), regardless of input format.
    public_key: Mapped[str] = mapped_column(Text)
    # SHA-256 (hex) of the DER SPKI; used for dedup and display.
    key_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=KeyStatus.pending.value, index=True
    )
    not_before: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    not_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
