# ADR-0010: Weekly digest email, not per-item reminders

**Status:** Accepted · 2026-09-07

## Context

The product's core value is reminders. The naive design sends one email per maintenance item as it
becomes due.

Resend's free tier caps at **3,000 emails/month and 100 per day**. The daily cap binds first: with
per-item alerts and ~8 tracked items per vehicle, we would exhaust 100/day at roughly 30 users. A
weekly digest — one email per user per week — supports around 700 users on the same tier, and login
emails (ADR-0009) share the same budget.

Independently, per-item alerts are worse product design: several separate emails in one week is the
fastest way to train a user to ignore us.

## Decision

A **weekly digest** per user, listing overdue, due-soon and upcoming items across all their
vehicles. Immediate per-item email is not built.

## Consequences

**Good:** ~23x more users on the free tier; no notification fatigue; a single well-designed email is
cheaper to build and test than a family of templates. A cost constraint and a UX improvement point
the same way, which is the best kind of constraint.

**Bad:** worst-case notification latency is 7 days, so a genuinely urgent item (an expiring
registration) could be surfaced late. Mitigation: the digest is scheduled relative to each user's
soonest due date rather than a fixed global day, and truly time-critical items are surfaced in the
dashboard, which is always current.

**Alerting:** warn at 70 emails/day so we learn about the ceiling before users do.

**Revisit when:** we exceed ~500 users, at which point a paid tier is justified by having users.
