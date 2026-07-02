import { NextRequest, NextResponse } from "next/server";
import { requireAuth } from "../../_lib/requireAuth";
import { getBackendConfig } from "../../_lib/backend-config";

// BFF proxy: /api/pm/<path> -> <STAFF_PORTAL_API_URL>/<path>, forwarding the
// staff Bearer token. This keeps the token in an httpOnly cookie (never in the
// browser) and lets the SPA call the staff-portal-api with same-origin requests.
async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const auth = requireAuth(req);
  if (auth instanceof NextResponse) return auth;

  const cfg = getBackendConfig();
  const { path } = await ctx.params;
  const search = req.nextUrl.search || "";
  const target = `${cfg.staffPortalApiUrl}/${(path || []).join("/")}${search}`;

  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await req.text() : undefined;

  const res = await fetch(target, {
    method,
    headers: auth.backendHeaders,
    body: body && body.length ? body : undefined,
    cache: "no-store",
  });

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
