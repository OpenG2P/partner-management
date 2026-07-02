import { NextRequest, NextResponse } from "next/server";

export interface AuthContext {
  accessToken: string;
  backendHeaders: Record<string, string>;
}

// Mirrors the staff-portal-ui contract: the IAM login flow sets httpOnly
// X-Access-Token / X-ID-Token cookies; API routes read them and forward the
// access token as a Bearer to backend services.
export function requireAuth(req: NextRequest): AuthContext | NextResponse {
  const accessToken = req.cookies.get("X-Access-Token")?.value;
  const idToken = req.cookies.get("X-ID-Token")?.value;

  if (!accessToken && !idToken) {
    return NextResponse.json(
      {
        errors: [
          {
            code: "G2P-AUT-LOGIN-REQUIRED",
            message: "Authentication required. No valid tokens found.",
          },
        ],
      },
      { status: 401 }
    );
  }

  if (!accessToken && idToken) {
    return NextResponse.json(
      {
        errors: [
          {
            code: "G2P-AUT-413",
            message:
              "Your access token exceeds the allowed size limit due to too many assigned roles. Please contact your administrator.",
          },
        ],
      },
      { status: 413 }
    );
  }

  return {
    accessToken: accessToken as string,
    backendHeaders: {
      "Content-Type": "application/json",
      accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  };
}
