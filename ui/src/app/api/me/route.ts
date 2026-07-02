import { NextRequest, NextResponse } from "next/server";
import { requireAuth } from "../_lib/requireAuth";
import { getBackendConfig } from "../_lib/backend-config";

export async function GET(req: NextRequest) {
  const auth = requireAuth(req);
  if (auth instanceof NextResponse) return auth;

  const cfg = getBackendConfig();
  const res = await fetch(`${cfg.iamUrl}/auth/get_user_profile`, {
    method: "GET",
    headers: auth.backendHeaders,
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
