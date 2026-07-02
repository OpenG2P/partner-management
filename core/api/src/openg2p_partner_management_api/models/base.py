import uuid
from datetime import datetime, timezone
from typing import Optional

from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    # Naive UTC to match the timestamp convention used across openg2p models.
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


class BaseModelWithId(BaseORMModel):
    """String-UUID primary key + created/updated timestamps.

    Mirrors the g2p-bridge / consent-manager base (UUID string PK) rather than
    the commons integer-PK base, so partner and key identifiers are opaque and
    safe to expose in URLs.
    """

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(), default=_utcnow, onupdate=_utcnow
    )

    def __init__(self, **kwargs):
        # Eagerly populate the PK so rows built in the same unit of work can
        # reference it before flush.
        if kwargs.get("id") is None:
            kwargs["id"] = str(uuid.uuid4())
        super().__init__(**kwargs)
