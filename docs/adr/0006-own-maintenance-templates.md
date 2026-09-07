# ADR-0006: Own generic maintenance templates; no paid schedule API

**Status:** Accepted · 2026-09-07

## Context

The natural product instinct is "decode the VIN, fetch the manufacturer's exact service schedule."
VIN decoding is genuinely free and unlimited via **NHTSA vPIC** (no API key). But vPIC returns
vehicle _identity_ — make, model, year, engine, plant. **It does not return maintenance schedules.**

OEM service schedules have no free source. Every provider surveyed is commercial (TorqueNode,
VehicleDatabases, Vehicle Finder); Edmunds' maintenance API is effectively gone. A product whose
core data comes from a paid API breaks the $0 constraint and creates lock-in on the single most
important dataset we have.

## Decision

Maintain our own **generic interval template table** in our database — 8 items at MVP, seeded by
migration, editable per vehicle by the user.

VIN decoding is deferred to post-MVP and scoped to _prefill convenience only_ (make/model/year).
Because vPIC responses take 2-3 seconds and rate-limit above roughly 5 req/s, any use must be
cached and must never sit in a blocking request path.

## Consequences

**Good:** $0, no vendor dependency on core data, no external call in the critical path, and full
control over interval semantics. Common intervals vary little across mainstream vehicles, so this
captures most of the real-world value.

**Bad:** intervals are approximate rather than manufacturer-exact. This is wrong for vehicles with
genuinely unusual schedules (e.g. long-life European oil intervals, EVs with no oil service at all).
User-editable intervals are the mitigation, and per-vehicle edits are a signal worth measuring: if
users edit intervals heavily, the generic defaults are too coarse and warrant revisiting.

**Revisit when:** interval-edit rate is high enough that a paid schedule API would demonstrably
improve retention — a decision to be made with data, and with revenue to pay for it.
