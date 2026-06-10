/**
 * Auth token refresh utility.
 *
 * When any API call returns 401, this module attempts to silently refresh
 * the access token via POST /api/v1/auth/refresh (which sends the httpOnly
 * refresh_token cookie on its /api/v1/auth path). On success the new cookies
 * are set by the server; on failure an event is dispatched that the layout
 * listens for to redirect to the login page.
 *
 * IMPORTANT: There is NO client-side token storage.  The access_token and
 * refresh_token are httpOnly cookies set by the backend.  We just need to
 * call the refresh endpoint and let the server handle the cookie rotation.
 */

let _refreshing: Promise<boolean> | null = null;
let _expired = false;

/**
 * Attempt to refresh the access token by calling POST /api/v1/auth/refresh.
 *
 * Uses a singleton promise so that concurrent 401s share a single refresh
 * attempt (prevents a thundering herd of refresh calls).
 * Returns false immediately if we already know the session is expired.
 */
export async function attemptTokenRefresh(): Promise<boolean> {
  if (_expired) return false;
  if (_refreshing) return _refreshing;

  _refreshing = _doRefresh();
  try {
    return await _refreshing;
  } finally {
    _refreshing = null;
  }
}

async function _doRefresh(): Promise<boolean> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const res = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) {
      dispatchAuthExpired();
      return false;
    }

    return true;
  } catch {
    dispatchAuthExpired();
    return false;
  }
}

/**
 * Dispatch a custom event that the dashboard layout listens for
 * to redirect to the login page. Only fires once to avoid loops.
 */
function dispatchAuthExpired() {
  if (typeof window === "undefined" || _expired) return;
  _expired = true;
  window.dispatchEvent(new CustomEvent("auth:expired"));
}

/**
 * Reset the expired flag — call after a successful login so that
 * subsequent 401s will attempt to refresh again.
 */
export function resetAuthExpired(): void {
  _expired = false;
  _refreshing = null;
}

/**
 * Add an event listener for auth expiry in layouts/pages.
 * Returns a cleanup function for use in useEffect.
 *
 * Usage:
 *   useEffect(() => {
 *     return listenForAuthExpired(() => router.push("/login"));
 *   }, [router]);
 */
export function listenForAuthExpired(handler: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("auth:expired", handler);
  return () => window.removeEventListener("auth:expired", handler);
}
