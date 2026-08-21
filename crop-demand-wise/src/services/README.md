# Services

All backend access lives here. UI components never call `fetch` directly.

```
src/services/
├── api/                     transport + typed endpoint wrappers
│   ├── config.ts            base URL, /api/v1 prefix, optional bearer token
│   ├── client.ts            fetch wrapper, ApiError, error-envelope parsing
│   ├── types.ts             wire types mirroring backend/openapi.json
│   ├── reference.service.ts /states /districts /crops /seasons /products
│   ├── farmer.service.ts    /farmer/*
│   ├── business.service.ts  /business/*
│   ├── rag.service.ts       /rag/query
│   ├── health.service.ts    /health, /health/db
│   └── index.ts             barrel — import from "@/services/api"
└── queries/                 React Query bindings over the services
    ├── keys.ts              query-key factory (single source for invalidation)
    ├── reference.queries.ts
    ├── farmer.queries.ts
    ├── business.queries.ts
    ├── rag.queries.ts
    └── index.ts             barrel — import from "@/services/queries"
```

## Layers

| Layer | Knows about | Doesn't know about |
| --- | --- | --- |
| `api/` | URLs, HTTP verbs, wire shapes | React, caching, components |
| `queries/` | caching, keys, enabled/retry policy | URLs, request bodies |
| routes / components | hooks and display | HTTP entirely |

Components import hooks from `@/services/queries`, and types from
`@/services/api`.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Backend origin. Default `http://localhost:8000`. |
| `VITE_API_TOKEN` | Optional bearer token for the endpoints the backend gates. |

The backend's `CORS_ORIGINS` must include this app's origin, or the browser
blocks every request before it reaches a route handler.

## Auth

This app has **no sign-in flow** and never calls `/auth/register` or
`/auth/login`. Most endpoints don't need a token:

| Endpoints | Token |
| --- | --- |
| `/health`, `/states`, `/districts`, `/crops`, `/seasons`, `/products` | not needed |
| `/farmer/*` | optional — without one, recorded intent rows have `user_id NULL` |
| `/business/*` | **required**, role `AGRI_BUSINESS` or `ADMIN` |
| `/rag/query` | **required**, any role |

When `VITE_API_TOKEN` is unset, the two gated groups return 401 and their
screens say what to configure. Everything else works.

## Adding an endpoint

1. Add its request/response types to `api/types.ts` (match `openapi.json`).
2. Add a method to the matching `*.service.ts`.
3. Add a key to `queries/keys.ts` and a hook to the matching `*.queries.ts`.
4. Export the hook from `queries/index.ts`.
