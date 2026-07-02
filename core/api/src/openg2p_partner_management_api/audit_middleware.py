"""Ships admin API calls to the central OpenG2P Audit Manager as CloudEvents.

This is the comprehensive, cross-platform forensic trail (complementing the
always-on local ``pm_audit_events`` ledger). It follows the OpenG2P reference
middleware contract:

* Off unless ``enabled`` AND a non-empty ``audit_manager_url``.
* Never blocks the response — emission is a fire-and-forget background task.
* Never raises — all failures are logged at WARNING and swallowed, so an Audit
  Manager outage cannot break the service.

Actor identity is recovered by decoding the request's Bearer token WITHOUT
signature verification (the JwtBearerAuth dependency already verified it for
accepted calls; for rejected calls we still want the attempted identity).
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
import jwt
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger("partner_management.audit")

_SKIP_PATHS = {"/ping", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
_EVENTS_PATH = "/v1/auditmanager/events"


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        audit_manager_url: str = "",
        enabled: bool = False,
        timeout_seconds: float = 2.0,
        source: str = "/openg2p/partner-management",
        module: str = "partner-management",
        client_id: str = "",
        audit_anonymous_failures: bool = True,
    ):
        super().__init__(app)
        self.enabled = bool(enabled and audit_manager_url)
        self.url = audit_manager_url.rstrip("/")
        self.timeout = timeout_seconds
        self.source = source
        self.module = module
        self.client_id = client_id
        self.audit_anonymous_failures = audit_anonymous_failures

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if not self.enabled:
            return response
        try:
            if request.method == "OPTIONS" or request.url.path in _SKIP_PATHS:
                return response
            event = self._build_event(request, response.status_code)
            if event is not None:
                asyncio.create_task(self._send(event))
        except Exception:  # never let auditing affect the response
            _logger.warning("Failed to build audit event", exc_info=True)
        return response

    # --- helpers -------------------------------------------------------------

    def _claims(self, request) -> dict | None:
        token = request.headers.get("Authorization", "")
        if not token.lower().startswith("bearer "):
            return None
        token = token[7:].strip()
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None

    def _build_event(self, request, status_code: int) -> dict | None:
        claims = self._claims(request)
        authenticated = claims is not None

        if not authenticated:
            # Only record anonymous calls that were rejected (attempted access).
            if not (self.audit_anonymous_failures and status_code >= 400):
                return None

        outcome = (
            "success"
            if status_code < 400
            else "denied"
            if status_code in (401, 403)
            else "failure"
        )

        route = request.scope.get("route")
        route_name = getattr(route, "name", "") or request.url.path
        action = route_name.split("_")[0] if route_name else request.method.lower()

        if authenticated:
            realm_roles = (claims.get("realm_access") or {}).get("roles") or []
            client_roles = (
                (claims.get("resource_access") or {}).get(self.client_id) or {}
            ).get("roles") or []
            actor = {
                "type": "user",
                "id": claims.get("sub") or "unknown",
                "name": claims.get("name"),
                "username": claims.get("preferred_username"),
                "roles": sorted(set(realm_roles) | set(client_roles)),
                "ip": self._client_ip(request),
                "session_id": claims.get("sid") or claims.get("session_state"),
            }
        else:
            actor = {"type": "anonymous", "id": "anonymous", "ip": self._client_ip(request)}

        return {
            "specversion": "1.0",
            "id": str(uuid.uuid4()),
            "source": self.source,
            "type": f"org.openg2p.{self.module}.{route_name}",
            "time": datetime.now(tz=timezone.utc).isoformat(),
            "datacontenttype": "application/json",
            "data": {
                "actor": actor,
                "action": action,
                "outcome": outcome,
                "context": {
                    "api": f"{request.method} {request.url.path}",
                    "module": self.module,
                    "http_status": status_code,
                    "request_id": request.headers.get("X-Request-ID"),
                },
            },
        }

    @staticmethod
    def _client_ip(request) -> str | None:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.headers.get("X-Real-IP") or (
            request.client.host if request.client else None
        )

    async def _send(self, event: dict):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(f"{self.url}{_EVENTS_PATH}", json=event)
        except Exception as e:
            _logger.warning("Audit Manager emit failed: %r", e)
