/**
 * apiClient.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Centralized HTTP client for the Bridgestone IT Agent frontend.
 *
 * Responsibilities:
 *  • Provides the single source-of-truth for API_BASE_URL (reads NEXT_PUBLIC_API_URL).
 *  • Distinguishes network errors (backend offline / ERR_CONNECTION_REFUSED) from
 *    application-level HTTP errors (4xx / 5xx).
 *  • Exports a typed `NetworkError` so callers can detect offline conditions without
 *    parsing error strings.
 *  • Keeps the browser console clean — network failures are intentionally NOT logged
 *    here; callers decide how to surface them.
 */

// ─── Base URL ────────────────────────────────────────────────────────────────

export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// ─── Error types ─────────────────────────────────────────────────────────────

/** Thrown when the browser cannot reach the backend at all (connection refused, DNS fail, etc.) */
export class NetworkError extends Error {
  readonly isNetworkError = true;
  constructor(message = "Backend is currently unavailable") {
    super(message);
    this.name = "NetworkError";
  }
}

/** Thrown when the backend responded but with a non-OK HTTP status. */
export class HttpError extends Error {
  readonly status: number;
  constructor(status: number, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "HttpError";
    this.status = status;
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isNetworkFailure(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("network request failed") ||
    msg.includes("econnrefused") ||
    msg.includes("connection refused")
  );
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────

export interface ApiRequestOptions extends RequestInit {
  /** If true, throws HttpError on non-OK responses. Defaults to false (caller checks .ok). */
  throwOnError?: boolean;
}

/**
 * Wraps `fetch` with:
 *  - Automatic `NetworkError` wrapping for connection-refused style failures.
 *  - Optional `throwOnError` to throw `HttpError` on non-2xx responses.
 *
 * Does NOT log anything — callers are responsible for UI feedback.
 */
export async function apiFetch(
  path: string,
  options: ApiRequestOptions = {}
): Promise<Response> {
  const { throwOnError = false, ...fetchOptions } = options;
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;

  let res: Response;
  try {
    res = await fetch(url, fetchOptions);
  } catch (err) {
    if (isNetworkFailure(err)) {
      throw new NetworkError();
    }
    throw err;
  }

  if (throwOnError && !res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.clone().json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new HttpError(res.status, detail);
  }

  return res;
}

/**
 * Convenience wrapper that adds an Authorization header.
 */
export async function authApiFetch(
  path: string,
  token: string,
  options: ApiRequestOptions = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
    Authorization: `Bearer ${token}`,
  };
  return apiFetch(path, { ...options, headers });
}
