# ADR-0005: Modular monolith plus one worker, not microservices

**Status:** Accepted · 2026-09-07

## Context

The project brief asks for an architecture capable of microservices, and explicitly warns against
adopting components for fashion. The obvious decomposition — `user-service`, `vehicle-service`,
`maintenance-service` — is the one most commonly reached for and, here, the wrong one.

Those three would share a single transactional boundary: creating a vehicle seeds its maintenance
plan in the **same transaction**. Splitting them turns an ACID insert into a distributed
transaction requiring sagas, compensating actions and eventual-consistency handling — solving a
coordination problem we would have created ourselves.

## Decision

Three deployables:

- **`api`** — FastAPI, a modular monolith with enforced internal boundaries
  (`app/identity/`, `app/vehicles/`, `app/maintenance/`)
- **`worker`** — ARQ consumer for scheduled and asynchronous work
- **`web`** — Next.js

`api` and `worker` are split because they have genuinely different failure modes, scaling curves
and deploy risk: nightly projection recomputation and digest fan-out must never occupy a
request-handling process. That is a real boundary, justified by runtime characteristics rather than
by domain nouns.

## Consequences

**Good:** one transaction, one migration path, one deploy for product changes. Async work is
isolated and independently scalable. Internal module boundaries mean extracting a service later is
mechanical.

**Bad:** `api` scales as a unit. A memory leak in one module affects all of them. Module boundaries
are a convention rather than a network boundary, so they need review discipline to avoid erosion —
specifically, no cross-module imports except through each module's public interface.

**Revisit when:** a single module demonstrably needs different scaling or availability from the
rest, backed by production metrics — not before.
