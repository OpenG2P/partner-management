"""Staff-realm admin authentication for the Partner Management admin APIs.

The UI logs users in through the IAM staff-portal flow and forwards the
Keycloak access token as ``Authorization: Bearer <jwt>``. ``JwtBearerAuth``
(openg2p-fastapi-auth) verifies the token signature/issuer/audience against the
configured staff realm; this subclass additionally requires the partner-manager
role. Issuer / JWKS / audience are configured via the COMMON_AUTH_* env vars.

The public key-fetch endpoints deliberately do NOT use this dependency: they
return only non-secret public material and must be callable without auth.
"""

import logging

from fastapi import Request
from openg2p_fastapi_auth.dependencies import JwtBearerAuth
from openg2p_fastapi_auth_models.schemas import AuthCredentials
from openg2p_fastapi_common.errors.http_exceptions import ForbiddenError

from .config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class PartnerManagerAuth(JwtBearerAuth):
    """Requires a valid staff-realm JWT carrying the partner-manager role."""

    async def __call__(self, request: Request) -> AuthCredentials | None:
        creds = await super().__call__(request)
        # None means auth is globally disabled (common_auth_enabled=false), e.g.
        # local dev — let the request through.
        if creds is None:
            return None

        required = (_config.auth_admin_role or "").strip()
        if required:
            claims = creds.model_dump()
            realm_roles = set((claims.get("realm_access") or {}).get("roles") or [])
            client_roles = set(
                (
                    (claims.get("resource_access") or {}).get(
                        _config.auth_admin_client_id
                    )
                    or {}
                ).get("roles")
                or []
            )
            if required not in (realm_roles | client_roles):
                raise ForbiddenError(
                    message=f"Forbidden. Missing required role '{required}'."
                )
        return creds

    @staticmethod
    def actor_info(creds: AuthCredentials | None) -> dict:
        """Identity for audit fields: {'id': sub, 'name': human-readable}.

        Both empty when auth is disabled (local dev). ``name`` prefers the login
        handle, then email, then the subject.
        """
        if not creds:
            return {"id": None, "name": None}
        data = creds.model_dump()
        return {
            "id": data.get("sub"),
            "name": data.get("preferred_username")
            or data.get("email")
            or data.get("sub"),
        }
