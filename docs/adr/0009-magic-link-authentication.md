# ADR-0009: Magic-link authentication, no passwords

**Status:** Accepted · 2026-09-07 · **Amended by**
[ADR-0014](0014-authentication-in-the-api.md) — magic links stand; Auth.js does not

## Context

Authentication is required for the MVP. Options: build email/password; use a managed provider
(Clerk, Auth0, Neon Auth); or use magic links via Auth.js with our own email sender.

We already need transactional email for maintenance reminders, so an email sender is not an
additional dependency. Managed providers introduce MAU caps and lock-in on the identity model,
which is expensive to reverse.

## Decision

**Magic links via Auth.js (NextAuth) with Resend as the sender.** FastAPI verifies the resulting
JWT against a JWKS endpoint. Short-lived access tokens with rotating refresh.

## Consequences

**Good:** no password storage, no hashing decisions, no password-reset flow, no credential-stuffing
surface — the single largest class of authentication vulnerability is removed by not having the
feature. Free, with no MAU ceiling. Email deliverability becomes a shared concern with reminders,
so effort spent there pays twice.

**Bad:** login depends on email delivery, so a Resend outage is a login outage — worth an alert.
Magic links in email are phishing-adjacent and must be short-lived (15 min), single-use, and
invalidated on use. Some users find them slower than a password manager. Resend's free tier allows
**100 emails/day**, shared with reminder digests, so login emails must be counted against that
budget (see ADR-0010).

**Reversal cost:** moderate — Auth.js supports adding providers without changing the user model.
