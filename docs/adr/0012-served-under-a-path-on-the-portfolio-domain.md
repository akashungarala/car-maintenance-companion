# ADR-0012: Served under a path on the portfolio domain

**Status:** Accepted · 2026-09-08 · Amends [ADR-0007](0007-frontend-on-vercel-hobby.md)

## Context

The original plan gave this project its own subdomains: `garage.akashungarala.com` for the app and
`api.garage.akashungarala.com` for the API. The founder already runs a portfolio site at
`akashungarala.com` which proxies another project — `/food-diary` — into a path on that domain, and
wanted this project to follow the same shape.

## Decision

The app is served at `akashungarala.com/apps/car-maintenance-companion` and the API at
`.../api`, both proxied by the portfolio project's Next.js `rewrites()`.

Making that work correctly requires three things, and getting any of them wrong produces a failure
that looks like something else:

1. **The frontend sets `basePath`** to the same prefix. The proxy then maps 1:1 and rewrites no
   paths, so links, asset URLs, form actions and redirects all stay valid. Without it the HTML
   loads and every `/_next/static` asset 404s — which reads as a broken deployment rather than a
   missing config line.
2. **The API sets FastAPI's `root_path`** to its prefix, because the proxy strips it. This changes
   only _generated_ URLs, so `/docs` fetches the proxied `openapi.json` while the routes themselves
   stay unprefixed and Kubernetes probes keep hitting `/health` directly on the pod.
3. **The API rewrite is ordered before the app's catch-all.** Rewrites match in order, and
   `/apps/car-maintenance-companion/:path*` would otherwise swallow the API path and answer API
   calls with a 404 HTML page instead of JSON.

## Consequences

**Good:** one domain, consistent with `/food-diary`. Frontend and API share an origin, so there is
no CORS to configure — a class of bug avoided rather than solved. Nothing is publicly reachable at
a URL this project owns alone, so the portfolio remains the single front door.

**Bad:** a deploy dependency in the other direction. Changing an origin means a portfolio PR and
deploy, and an outage there takes this project down with it. The prefix is compiled into the
frontend build, so it is not a runtime setting — changing the URL means rebuilding.

**Removed:** `Strict-Transport-Security` from this app. Served under a path on a domain it does not
own, an HSTS header here would set policy for the whole parent domain and every subdomain of it,
including ones this project knows nothing about. That header belongs to the project that owns the
domain.

**Unused but retained:** the `garage.akashungarala.com` DNS record. The frontend is now proxied to
its Vercel origin directly, so nothing resolves there — but it stays as the target for the ADR-0007
escape hatch if the frontend ever moves into the cluster. `api.garage.akashungarala.com` remains in
use as the API origin the portfolio proxies to.
