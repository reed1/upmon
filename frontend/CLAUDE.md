# Upmon Frontend

Vue 3 + Vite + Tailwind CSS v4 SPA for displaying monitor status. Built dist is served by the backend at `/frontend`.

## Dev & Build

```
npm install
npm run dev        # local dev server
npm run build      # production build to dist/
```

## Architecture

- Vite `base: '/frontend/'` so assets resolve correctly under the subpath
- `src/api.ts` — `fetchStatus(projectId)` helper calling `/api/v1/status` with `x-api-key` header
- `src/types.ts` — shared TypeScript interfaces for API responses (`SiteStatus`, `DayEntry`, `DailySummaryResponse`)
- API base URL and key are baked in at build time via Vite env vars

## Environment

Env vars prefixed with `VITE_` are embedded at build time. `.env` has defaults, `.env.local` (gitignored) for overrides.

- `VITE_API_BASE_URL` — backend base URL (e.g. `https://upmon.r-mulyadi.com`)
- `VITE_API_KEY` — API key for backend authentication
