/**
 * API configuration.
 *
 * Base URL points at the FastAPI backend (`backend/main.py`, default
 * http://localhost:8000). Override per environment with VITE_API_BASE_URL.
 *
 * NOTE: the backend's CORS_ORIGINS must include this app's origin, or requests
 * fail in the browser before reaching a route handler.
 */
const DEFAULT_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (import.meta.env["VITE_API_BASE_URL"] ?? DEFAULT_BASE_URL).replace(
  /\/+$/,
  "",
);

/** All versioned endpoints live under this prefix; /health does not. */
export const API_V1 = "/api/v1";

/**
 * Optional bearer token.
 *
 * This app has no sign-in flow and does not call /auth/*. One endpoint group
 * is still gated server-side — /rag/query wants any authenticated user — so
 * the token is supplied as configuration instead. Leave it unset and the Ask
 * screen shows the API's own 401 with what to configure; every other endpoint,
 * /business/* included, works without it.
 *
 * Mint one against your database with:
 *   cd backend && .venv/bin/python -c "from app.security import create_access_token; \
 *     print(create_access_token(user_id=<id>, role='AGRI_BUSINESS', district_id=None))"
 */
export const API_TOKEN: string | null = import.meta.env["VITE_API_TOKEN"] ?? null;
