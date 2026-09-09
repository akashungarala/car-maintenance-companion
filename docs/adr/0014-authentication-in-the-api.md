# ADR-0014: Authentication belongs in the API, not Auth.js

- Status: Accepted
- Date: 2026-09-09
- Amends: [ADR-0009](0009-magic-link-authentication.md) — the magic-link decision stands; the
  mechanism does not

## Context

ADR-0009 chose magic links via Auth.js (NextAuth), with Resend as the sender and FastAPI verifying
the resulting JWT. That is a conventional and sensible arrangement, and it cannot be built here.

Auth.js's email provider **requires a database adapter**. Magic links depend on storing a
verification token server-side so the callback can look it up exactly once. There is no JWT-only
mode for this provider, because a stateless token cannot be invalidated after a single use — which
is precisely the property a magic link needs.

Auth.js runs in the Next.js app, which is deployed on Vercel. Our PostgreSQL is a CloudNativePG
cluster reachable only inside the Kubernetes cluster: three `ClusterIP` services, no ingress rule
for 5432, and an origin firewalled to Cloudflare's ranges. Vercel functions cannot reach it, and
the fix would be exposing Postgres to the public internet — undoing a deliberate security posture
in order to satisfy a library.

The alternative fix, having Auth.js call our API through a custom adapter, means writing and
maintaining an adapter whose only purpose is to proxy to endpoints we would then have written
anyway. That is the whole feature plus a translation layer.

## Decision

**Implement magic-link authentication in the FastAPI service.** Three endpoints — request the
link, exchange it for a session, sign out — with the session carried in an `httpOnly`, `Secure`,
`SameSite=Lax` cookie issued by the API.

The frontend holds no token and makes no authentication decision. It calls the API and reacts to 401.

## Consequences

Good:

- Postgres stays unreachable from the internet. The security decision drives the architecture,
  rather than being traded away for a library's convenience.
- Everything already built applies unchanged. The rate limiter is Redis-backed and the strictest
  bucket (5/min) was written for exactly these endpoints; requests are traced, logged with
  `trace_id`, and counted; the token table is an ordinary Alembic migration with the same
  round-trip test as everything else.
- One language owns identity. There is no second session model in TypeScript to keep consistent
  with the first, and no JWKS endpoint to publish, rotate and verify against.
- Sessions can be revoked. A server-side session is a row; a stateless JWT is valid until it
  expires no matter what happens in between.

Bad, and accepted:

- We write the flow ourselves: token generation, hashing at rest, single-use enforcement, expiry,
  cookie flags. That is genuinely more code than configuring a provider, and each piece is a place
  to get security wrong. It is mitigated by the flow being small and by every rule being asserted
  in a test — not by assuming care.
- Adding Google or GitHub sign-in later means implementing OAuth rather than adding a line of
  Auth.js configuration. Accepted: no OAuth provider is planned, and if one is ever needed it can
  be added beside this rather than replacing it.
- ADR-0009's "reversal cost: moderate" was justified by Auth.js supporting extra providers. That
  justification no longer holds, and the honest cost is higher.

Unchanged from ADR-0009: magic links, no passwords, 15-minute single-use links, Resend as the
sender, and login emails counted against the same 100/day budget as reminder digests.
