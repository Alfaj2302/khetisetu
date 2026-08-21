/**
 * HTTP client for the KhetiSetu API.
 *
 * Every backend error comes back in one envelope (see `backend/app/errors.py`):
 *   { "error": { "code": "...", "message": "..." } }
 * so `ApiError` carries that code/message straight through to the UI instead of
 * each caller re-parsing the body.
 */
import { API_BASE_URL, API_TOKEN } from "./config";

export interface ApiErrorEnvelope {
  error: { code: string; message: string };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** The request never reached the API (offline, DNS, CORS preflight refused). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** 401/403 — this endpoint needs a bearer token the app wasn't configured with. */
  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/** True when a token is configured, so screens can explain themselves up front. */
export const hasApiToken = API_TOKEN !== null && API_TOKEN !== "";

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  query?: QueryParams;
  body?: unknown;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: QueryParams): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    // Skip unset filters so `?year=undefined` never reaches the API.
    if (value === undefined || value === null || value === "") continue;
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function readError(response: Response): Promise<ApiError> {
  let code = "ERROR";
  let message = response.statusText || `Request failed with status ${response.status}`;
  try {
    const body = (await response.json()) as Partial<ApiErrorEnvelope>;
    if (body.error?.code) code = body.error.code;
    if (body.error?.message) message = body.error.message;
  } catch {
    // Non-JSON error body (a proxy 502, an HTML error page) — keep the status text.
  }
  return new ApiError(response.status, code, message);
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { query, body, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (hasApiToken) headers["Authorization"] = `Bearer ${API_TOKEN}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      ...(signal ? { signal } : {}),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      `Could not reach the KhetiSetu API at ${API_BASE_URL}. Check that the backend is running and that its CORS_ORIGINS allows this origin.`,
    );
  }

  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, query?: QueryParams, options?: Omit<RequestOptions, "query" | "body">) =>
    request<T>("GET", path, { ...options, ...(query ? { query } : {}) }),

  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">) =>
    request<T>("POST", path, { ...options, ...(body === undefined ? {} : { body }) }),
};
