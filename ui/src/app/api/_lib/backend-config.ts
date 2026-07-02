import "server-only";

// Server-side backend configuration (used only inside /api route handlers).
export function getBackendConfig() {
  return {
    iamUrl: process.env.IAM_URL ?? "",
    keycloakLogoutUrl: process.env.KEYCLOAK_LOGOUT_URL ?? "",
    loginProviderId: process.env.LOGIN_PROVIDER_ID ?? "",
    cookieDomain: process.env.COOKIE_DOMAIN ?? "",
    redirectUrl: process.env.REDIRECT_URL ?? "",
    // This repo's staff-portal-api (domain calls). Login/profile/logout go to
    // the shared commons IAM via iamUrl above (NSR pattern).
    staffPortalApiUrl: process.env.STAFF_PORTAL_API_URL ?? "",
  };
}
