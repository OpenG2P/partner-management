"""Staff-realm admin authentication for the Partner Management admin APIs.

The UI logs users in through the IAM staff-portal flow and forwards the
Keycloak access token as ``Authorization: Bearer <jwt>``. ``JwtBearerAuth``
verifies the token signature/issuer/audience against the configured staff
realm; ``PartnerManagerAuth`` additionally requires the partner-manager role.
Issuer / JWKS / audience are configured via COMMON_AUTH_* (or
PARTNER_MANAGER_AUTH_*) env vars.

The public key-fetch endpoints deliberately do NOT use this dependency: they
return only non-secret public material and must be callable without auth.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import datetime

import httpx
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import ConfigDict

from openg2p_fastapi_common.errors.http_exceptions import (
    ForbiddenError,
    InternalServerError,
    UnauthorizedError,
)

from .config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)

_jwks_cache: ContextVar[dict | None] = ContextVar("jwks_cache", default=None)


class AuthCredentials(HTTPAuthorizationCredentials):
    model_config = ConfigDict(extra="allow")

    scheme: str = "bearer"
    credentials: str
    iss: str = None
    sub: str = None
    user_type: str | None = None
    aud: str | list | None = None
    iat: datetime | None = None
    exp: datetime | None = None


class JwtBearerAuth(HTTPBearer):
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        config_dict = _config.model_dump()
        if not config_dict.get("auth_enabled", None):
            return None

        api_call_name = str(request.scope["route"].name)

        api_auth_settings = config_dict.get("auth_api_" + api_call_name, {})

        if (not api_auth_settings) or (not api_auth_settings.get("enabled", None)):
            print("Auth not enabled for this API call:", api_call_name)

        issuers_list = api_auth_settings.get("issuers", None) or config_dict.get("auth_default_issuers", [])
        audiences_list = api_auth_settings.get("audiences", None) or config_dict.get(
            "auth_default_audiences", []
        )
        jwks_urls_list = api_auth_settings.get("jwks_urls", None) or config_dict.get(
            "auth_default_jwks_urls", []
        )

        jwt_token = request.headers.get("Authorization", None) or request.cookies.get("X-Access-Token", None)
        jwt_id_token = request.cookies.get("X-ID-Token", None)
        if jwt_token:
            jwt_token = jwt_token.removeprefix("Bearer ")

        if not jwt_token:
            raise UnauthorizedError()

        try:
            unverified_payload = jwt.get_unverified_claims(jwt_token)
        except Exception as e:
            raise UnauthorizedError(message=f"Unauthorized. Jwt expired. {repr(e)}") from e
        iss = unverified_payload.get("iss", None)
        aud = unverified_payload.get("aud", None)
        if (not iss) or (iss not in issuers_list):
            raise UnauthorizedError(message=f"Unauthorized. Unknown Issuer. {iss}")

        if audiences_list:
            if (
                (not aud)
                or (isinstance(aud, list) and not (set(audiences_list).issubset(set(aud))))
                or (isinstance(aud, str) and aud not in audiences_list)
            ):
                raise UnauthorizedError(message="Unauthorized. Unknown Audience.")

        jc = _jwks_cache.get()
        if not jc:
            jc = {}
            _jwks_cache.set(jc)
        jwks = jc.get(iss, None)

        if not jwks:
            try:
                jwks_list_index = list(issuers_list).index(iss)
                jwks_url = (
                    jwks_urls_list[jwks_list_index]
                    if jwks_list_index < len(jwks_urls_list)
                    else iss.rstrip("/") + "/.well-known/jwks.json"
                )

                res = httpx.get(jwks_url)
                res.raise_for_status()
                jwks = res.json()
                jc[iss] = jwks
            except Exception as e:
                raise InternalServerError(
                    code="G2P-AUT-500",
                    message=f"Something went wrong while trying to fetch Jwks. {repr(e)}",
                ) from e

        try:
            jwt.decode(
                jwt_token,
                jwks,
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_sub": False,
                },
            )
        except Exception as e:
            raise UnauthorizedError(message=f"Unauthorized. Invalid Jwt. {repr(e)}") from e

        if jwt_id_token:
            try:
                res = jwt.decode(
                    jwt_id_token,
                    jwks,
                    access_token=jwt_token,
                    options={
                        "verify_aud": False,
                        "verify_iss": False,
                        "verify_sub": False,
                        "verify_at_hash": api_auth_settings.get(
                            "id_token_verify_at_hash",
                            config_dict.get("auth_default_id_token_verify_at_hash", True),
                        ),
                    },
                )
                unverified_payload = self.combine_tokens(unverified_payload, res)
            except Exception as e:
                raise UnauthorizedError(message=f"Unauthorized. Invalid Jwt ID Token. {repr(e)}") from e

        claim_to_check = api_auth_settings.get("claim_name", None)
        claim_values = api_auth_settings.get("claim_values", None)
        if claim_to_check:
            claims = unverified_payload.get(claim_to_check, None)
            if not claims:
                raise ForbiddenError(message="Forbidden. Claim(s) missing.")
            if isinstance(claims, str):
                if len(claim_values) != 1 or claim_values[0] != claims:
                    raise ForbiddenError(message="Forbidden. Claim doesn't match.")
            else:
                if all(x in claims for x in claim_values):
                    raise ForbiddenError(message="Forbidden. Claim(s) don't match.")

        unverified_payload["credentials"] = jwt_token

        return AuthCredentials.model_validate(unverified_payload)

    @classmethod
    def combine_token_dicts(cls, *token_dicts) -> dict:
        res = None
        for token_dict in token_dicts:
            if token_dict:
                if not res:
                    res = token_dict
                else:
                    for k, v in token_dict.items():
                        if v:
                            res[k] = v
        return res

    @classmethod
    def combine_tokens(cls, *tokens) -> dict:
        res = []
        for token in tokens:
            if token:
                try:
                    res.append(jwt.get_unverified_claims(token) if isinstance(token, str) else token)
                except Exception:
                    pass
        return cls.combine_token_dicts(*res)


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
