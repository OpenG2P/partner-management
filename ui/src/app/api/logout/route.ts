import { NextRequest, NextResponse } from "next/server";
import { requireAuth } from "../_lib/requireAuth";
import { getBackendConfig } from "../_lib/backend-config";

export async function GET(req: NextRequest) {
  const cfg = getBackendConfig();
  const auth = requireAuth(req);
  const idToken = req.cookies.get("X-ID-Token")?.value;

  const logoutUrl =
    `${cfg.keycloakLogoutUrl}` +
    `?post_logout_redirect_uri=${encodeURIComponent(cfg.redirectUrl)}` +
    (idToken ? `&id_token_hint=${idToken}` : "");

  if (!(auth instanceof NextResponse)) {
    try {
      await fetch(`${cfg.iamUrl}/auth/logout`, {
        method: "POST",
        headers: auth.backendHeaders,
      });
    } catch {
      /* best-effort */
    }
  }

  const res = NextResponse.redirect(logoutUrl);
  for (const name of ["X-Access-Token", "X-ID-Token"]) {
    res.cookies.delete({ name, path: "/", domain: cfg.cookieDomain || undefined });
  }
  return res;
}
