const ORG_KEY = "sovereign.org";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function getActiveOrg(): string | null {
  try {
    return localStorage.getItem(ORG_KEY);
  } catch {
    return null;
  }
}

export function setActiveOrg(id: string | null) {
  try {
    if (id) localStorage.setItem(ORG_KEY, id);
    else localStorage.removeItem(ORG_KEY);
  } catch {
    // Storage unavailable (private mode): the org is chosen again on next load.
  }
}

/** Fetch from the API. Adds the active organization; the session cookie travels on its own. */
export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const org = getActiveOrg();
  if (org) headers.set("X-Organization-Id", org);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      // not JSON
    }
    if (response.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
      window.location.href = "/login";
    }
    throw new ApiError(response.status, code, message);
  }
  return response;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  return response.status === 204 ? (undefined as T) : response.json();
}

export const json = (body: unknown) => JSON.stringify(body);

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
