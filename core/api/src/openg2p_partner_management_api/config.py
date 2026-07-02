from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic_settings import SettingsConfigDict

from . import __version__


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
    # JWKS / audience are configured via the COMMON_AUTH_* env vars consumed by
    # openg2p-fastapi-auth. Set auth_admin_role="" to require only a valid token.
    auth_admin_role: str = "partner_manager"
    auth_admin_client_id: str = "partner-management"

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
