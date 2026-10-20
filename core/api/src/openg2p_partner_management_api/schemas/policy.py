import re
from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ..config import Settings
from ..models import IDENTIFIER_PATTERN, FetchType, SigningAlgorithm
from .key import blank_to_none

# Policy durations are stored in VARCHAR(32) columns.
_DURATION_MAX_LEN = 32
_DURATION_RE = re.compile(
    r"^P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<weeks>\d+)W)?"
    r"(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)
# A use-case grant names one major version of a published use case: name@major.
USE_CASE_PATTERN = r"^[^\s/?#%@]+@\d+$"
DEFAULT_SIGNING_ALGS = ["EdDSA", "ES256"]


def allowed_signing_algorithms() -> List[str]:
    """Algorithms a policy may allow: PM's key algorithms narrowed by
    ``crypto_allowed_algorithms``. A policy can only narrow this set."""
    allowed = {a.strip() for a in Settings.get_config().crypto_allowed_algorithms}
    return [a.value for a in SigningAlgorithm if a.value in allowed]


def iso_duration_to_timedelta(duration: str) -> timedelta:
    """Parse a (subset of) ISO-8601 duration. Years ~ 365 days, months ~ 30 days."""
    match = _DURATION_RE.match(duration.strip())
    if not match:
        raise ValueError(f"Invalid ISO-8601 duration: {duration!r}")
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    return timedelta(
        days=parts.get("years", 0) * 365
        + parts.get("months", 0) * 30
        + parts.get("weeks", 0) * 7
        + parts.get("days", 0),
        hours=parts.get("hours", 0),
        minutes=parts.get("minutes", 0),
        seconds=parts.get("seconds", 0),
    )


def duration_problem(value: Optional[str]) -> Optional[str]:
    """Why ``value`` is not a usable policy duration, or None if it is (or unset)."""
    if value is None:
        return None
    if len(value) > _DURATION_MAX_LEN:
        return f"longer than {_DURATION_MAX_LEN} characters"
    try:
        delta = iso_duration_to_timedelta(value)
    except ValueError:
        return "not an ISO-8601 duration such as P30D, P1Y or PT12H"
    if delta.total_seconds() <= 0:
        return "must be longer than zero"
    return None


def _clean_list(values: List[str]) -> List[str]:
    """Trim entries, drop blanks and duplicates (keeps the given order)."""
    out: List[str] = []
    for v in values:
        v = v.strip()
        if v and v not in out:
            out.append(v)
    return out


class PolicyInput(BaseModel):
    """One policy proposed by an onboarding or policy request.

    - ``data_controller`` set (e.g. ``farmer_registry``): a scope policy for that
      registry — ``allowed_data_scopes`` required, ``allowed_use_cases`` empty.
    - ``data_controller`` null / "": a use-case policy (an exchange) —
      ``allowed_use_cases`` (``name@major``) required, ``allowed_data_scopes`` empty.
    - purposes / subject id types: open sets; empty = any.
    - ``allowed_signing_algs``: at least one of ``GET /metadata`` → ``signing_algorithms``.
    - durations: ISO-8601 (``P30D``, ``P1Y``, ``PT12H``), > 0, or null.
    Lists are trimmed, blanks and duplicates dropped.
    """

    model_config = ConfigDict(use_enum_values=True)

    data_controller: Optional[str] = Field(
        default=None, max_length=255, pattern=IDENTIFIER_PATTERN, examples=["farmer_registry"]
    )
    allowed_data_scopes: List[str] = Field(default_factory=list)
    allowed_use_cases: List[str] = Field(default_factory=list, examples=[["loan-profile@1"]])
    allowed_purposes: List[str] = Field(default_factory=list)
    allowed_subject_id_types: List[str] = Field(default_factory=list)
    allowed_signing_algs: List[str] = Field(default_factory=lambda: list(DEFAULT_SIGNING_ALGS))
    max_validity_duration: Optional[str] = Field(default=None, examples=["P1Y"])
    fetch_type: FetchType = FetchType.oneshot
    max_fetch_frequency: Optional[str] = None
    data_life: Optional[str] = Field(default=None, examples=["P30D"])

    @field_validator("data_controller", mode="before")
    @classmethod
    def _blank_controller(cls, value):
        value = blank_to_none(value)
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "allowed_data_scopes", "allowed_use_cases", "allowed_purposes",
        "allowed_subject_id_types", "allowed_signing_algs",
    )
    @classmethod
    def _clean(cls, values: List[str]) -> List[str]:
        return _clean_list(values)

    # Error messages name the field: the platform's error handler returns only
    # the message, not its location.
    @field_validator("allowed_use_cases")
    @classmethod
    def _use_case_refs(cls, values: List[str]) -> List[str]:
        bad = [v for v in values if not re.match(USE_CASE_PATTERN, v)]
        if bad:
            raise ValueError(
                f"allowed_use_cases: {bad} must be 'name@major' (e.g. loan-profile@1)"
            )
        return values

    @field_validator("allowed_signing_algs")
    @classmethod
    def _known_algs(cls, values: List[str]) -> List[str]:
        allowed = allowed_signing_algorithms()
        bad = [v for v in values if v not in allowed]
        if bad:
            raise ValueError(f"allowed_signing_algs: unsupported {bad}; allowed: {allowed}")
        if not values:
            raise ValueError("allowed_signing_algs: at least one algorithm is required")
        return values

    @field_validator("fetch_type", mode="before")
    @classmethod
    def _fetch_type(cls, value):
        types = [f.value for f in FetchType]
        if value not in types:
            raise ValueError(f"fetch_type: {value!r} is not one of {types}")
        return value

    @field_validator("max_validity_duration", "max_fetch_frequency", "data_life", mode="before")
    @classmethod
    def _duration(cls, value, info: ValidationInfo):
        if isinstance(value, str):
            value = value.strip().upper() or None
        problem = duration_problem(value)
        if problem:
            raise ValueError(f"{info.field_name}: {value!r} {problem}")
        return value

    @model_validator(mode="after")
    def _scope_or_use_case(self):
        if self.data_controller:
            if not self.allowed_data_scopes:
                raise ValueError(
                    f"allowed_data_scopes: required for data controller '{self.data_controller}'"
                )
            if self.allowed_use_cases:
                raise ValueError(
                    "allowed_use_cases: only for a use-case policy (no data controller)"
                )
        else:
            if not self.allowed_use_cases:
                raise ValueError("allowed_use_cases: required for a use-case policy")
            if self.allowed_data_scopes:
                raise ValueError(
                    "allowed_data_scopes: only for a data controller's policy "
                    "(set data_controller)"
                )
        return self


def check_distinct_controllers(policies: List[PolicyInput]) -> List[PolicyInput]:
    """At most one policy per data controller (null counts once) in a request."""
    seen, dup = set(), set()
    for p in policies:
        if p.data_controller in seen:
            dup.add(p.data_controller or "(use cases)")
        seen.add(p.data_controller)
    if dup:
        raise ValueError(f"policies: more than one policy for {sorted(dup)}")
    return policies


class PolicyOut(BaseModel):
    """A partner's active policy, as served to other modules by ``GET /policies``."""

    model_config = ConfigDict(from_attributes=True)

    partner_id: str
    data_controller: Optional[str] = None
    version: int
    allowed_data_scopes: List[str] = Field(default_factory=list)
    allowed_use_cases: List[str] = Field(default_factory=list)
    allowed_purposes: List[str] = Field(default_factory=list)
    allowed_subject_id_types: List[str] = Field(default_factory=list)
    allowed_signing_algs: List[str] = Field(default_factory=list)
    max_validity_duration: Optional[str] = None
    fetch_type: str
    max_fetch_frequency: Optional[str] = None
    data_life: Optional[str] = None
    effective_from: Optional[datetime] = None


class PartnerPoliciesOut(BaseModel):
    partner_id: str
    policies: List[PolicyOut]


class PolicyListOut(BaseModel):
    count: int
    policies: List[PolicyOut]


class PolicyResponse(PolicyOut):
    """Staff view of one policy version (any status)."""

    id: str
    status: str  # pending | active | superseded | rejected | revoked
    request_id: str
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: datetime
