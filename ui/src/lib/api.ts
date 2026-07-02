// Thin client over the BFF proxy. On 401 it dispatches an event the AuthProvider
// listens for to trigger re-login.
function emitUnauthorized() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("auth:unauthorized"));
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    emitUnauthorized();
    throw new Error("Unauthorized");
  }
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const msg =
      (data && data.errors && data.errors[0]?.message) ||
      (data && data.message) ||
      `Request failed: ${res.status}`;
    throw new Error(msg);
  }
  return data as T;
}

const base = "/api/pm";

export const api = {
  get: <T = unknown>(path: string): Promise<T> =>
    fetch(`${base}${path}`, { credentials: "include" }).then(handle<T>),

  post: <T = unknown>(path: string, body?: unknown): Promise<T> =>
    fetch(`${base}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then(handle<T>),
};
