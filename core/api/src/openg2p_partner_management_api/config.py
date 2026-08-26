from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic import model_validator
from pydantic_settings import SettingsConfigDict

from . import __version__

_COMMON_AUTH_ENV = {
    "auth_enabled": "COMMON_AUTH_ENABLED",
    "auth_default_issuers": "COMMON_AUTH_DEFAULT_ISSUERS",
    "auth_default_audiences": "COMMON_AUTH_DEFAULT_AUDIENCES",
    "auth_default_jwks_urls": "COMMON_AUTH_DEFAULT_JWKS_URLS",
    "auth_default_id_token_verify_at_hash": "COMMON_AUTH_DEFAULT_ID_TOKEN_VERIFY_AT_HASH",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="partner_manager_", env_file=".env", extra="allow"
    )

    openapi_title: str = "OpenG2P Partner Management API"
    openapi_description: str = """
    Central registry of OpenG2P partners and their public keys.

    All OpenG2P modules (g2p-bridge, consent-manager, ...) fetch partner
    public keys from this service instead of maintaining their own partner
    tables. Admin (staff-realm) APIs onboard partners and rotate keys through a
    simple created -> active -> disabled lifecycle. The key-fetch APIs are
    unauthenticated (they only return non-secret public material) and are
    exposed on the cluster-internal gateway.
    ***********************************
    Further details are in the GitBook: Platform Services > Partner Management.
    ***********************************
    """
    openapi_version: str = __version__

    db_dbname: str = "openg2p_partner_management_db"

    # --- Key material policy -------------------------------------------------
    # Signature algorithms accepted on input and advertised on the JWKS view.
    crypto_allowed_algorithms: list[str] = ["RS256", "ES256", "EdDSA"]
    # RSA keys weaker than this (bits) are rejected at onboarding.
    min_rsa_key_size: int = 2048
    # Timeout (seconds) when importing keys from a partner's jwks_url.
    jwks_fetch_timeout: int = 10

    # --- Public key-fetch API ------------------------------------------------
    # Cache-Control max-age (seconds) returned on key-fetch responses so callers
    # (e.g. the commons PartnerKeyStore) cache within a bounded rotation window.
    key_fetch_cache_max_age: int = 300

    # --- Admin auth (Keycloak staff realm) -----------------------------------
    # A caller must present a staff-realm JWT carrying this role (realm role or a
    # client role under auth_admin_client_id) to use the admin APIs. JWT issuer /
    # JWKS / audience are configured via COMMON_AUTH_* (Helm) or
    # PARTNER_MANAGER_AUTH_*. Set auth_admin_role="" to require only a valid token.
    auth_admin_role: str = "partner_manager"
    auth_admin_client_id: str = "partner-management"
    auth_enabled: bool = True
    auth_default_issuers: list[str] = []
    auth_default_audiences: list[str] = []
    auth_default_jwks_urls: list[str] = []
    auth_default_id_token_verify_at_hash: bool = True

    # --- Central Audit Manager (long-term forensic trail) --------------------
    # Off by default; emission requires audit_enabled=true AND a manager URL.
    # Delivery is fire-and-forget and never blocks or fails a request. This is
    # complementary to the local pm_audit_events ledger, which is always on.
    audit_enabled: bool = False
    audit_manager_url: str = ""
    audit_timeout_seconds: float = 2.0
    audit_source: str = "/openg2p/partner-management"
    audit_module: str = "partner-management"
    audit_anonymous_failures: bool = True

    @model_validator(mode="before")
    @classmethod
    def absorb_common_auth_env(cls, data):
        """Helm still sets COMMON_AUTH_*; honour those when partner_manager_ is unset."""
        import os

        if data is None:
            data = {}
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for field, env_name in _COMMON_AUTH_ENV.items():
            if field in out:
                continue
            value = os.getenv(env_name)
            if value is not None:
                out[field] = value
        return out
