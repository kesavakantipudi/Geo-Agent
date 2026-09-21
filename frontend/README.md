# frontend/

Next.js 15 / React 19 / TypeScript (strict) / Tailwind CSS 3 web client for GeoAgent (Phases 2–3).

## Stack

- **Next.js 15** (App Router, `src/` layout) with a small Edge `middleware.ts` that guards `/dashboard` routes on the `geoagent_access` session cookie.
- **Leaflet 1.9 + react-leaflet 5 + leaflet-draw** for the map canvas, AOI drawing, and place pins (Phase 3).
- **Tailwind CSS 3.4** for styling; **lucide-react** for icons; **clsx** for class merging.
- **ESLint 9** (flat config via `eslint-config-next`) and `tsc --noEmit` for checks.

## Layout

```
src/
  app/
    layout.tsx            Root layout, mounts the AuthProvider
    page.tsx              Public landing page
    login/page.tsx        Sign-in form (posts to /api/v1/auth/login)
    dashboard/layout.tsx  App shell (sidebar, header, sign-out)
    dashboard/{index,analysis,history,settings}/page.tsx
  components/
    AppShell.tsx
    map/LocationMap.tsx   Map + tile layer, AOI draw handlers, overlay, place pin
    map/PlaceSearch.tsx   Debounced, cancellable place search dropdown
    map/AoiPanel.tsx      Draw / import / paste / export / clear AOI, validation info
    analysis/AnalysisConfigPanel.tsx  Title, workspace, dates, agents, save
    analysis/SessionsList.tsx         Session list with reopen
    analysis/AnalysisWorkspace.tsx    Orchestrates the analysis page
  middleware.ts           Cookie guard for /dashboard
  lib/
    api/client.ts         Typed fetch wrapper (JSON error shape, 401 -> refresh once, AbortSignal)
    api/types.ts          Mirrors backend API response shapes
    api/geo.ts            Phase 3 calls: places, geometries/validate, analysis sessions
    map/config.ts         Env-configurable tile URL / attribution / max zoom
    map/geojson.ts        Geometry extraction + GeoJSON export helpers
    auth.tsx              AuthProvider / useAuth (bootstrap /users/me, logout, reload)
```

## Development

```bash
npm install
npm run dev        # http://localhost:3000
```

The Next dev server proxies `/api/*` to the backend (`http://localhost:8000` by default)
via `next.config.ts` rewrites, so HTTP-only auth cookies stay SameSite-compatible on one
origin. Point `BACKEND_URL` elsewhere if the API is not on `localhost:8000`.

Map tiles default to OpenStreetMap and are configurable through `NEXT_PUBLIC_MAP_TILE_URL`,
`NEXT_PUBLIC_MAP_TILE_ATTRIBUTION`, and `NEXT_PUBLIC_MAP_TILE_MAX_ZOOM` (see
`.env.local.example`). The map is mounted with `next/dynamic` (`ssr: false`) because Leaflet
requires the browser DOM.

## Checks

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # eslint .
npm run build       # production build
```

## Container

`frontend/Dockerfile` builds and serves the app with `next start`; `BACKEND_URL` is a build
argument (defaults to `http://backend:8000` so `docker-compose` services resolve each other).

See [`../DEVELOPMENT.md`](../DEVELOPMENT.md) and [`../README.md`](../README.md).