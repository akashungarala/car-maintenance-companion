# Testing & TDD

There is **no QA role**. The engineer implementing a change owns its tests. A change without
appropriate automated tests is not complete, and CI enforces that rather than trusting intent.

## The TDD contract

**RED → GREEN → REFACTOR**, and the git history should show it.

A commit that adds behaviour without a test that failed first is not acceptable. The practical
test when reviewing your own work: _could I have written this test before the implementation, and
did I?_ If the answer is no, the test was probably shaped by the implementation and will pass for
the wrong reasons.

What this rule is **not**: a demand for 100% coverage, tests for getters, or tests that assert an
implementation calls a particular private method. Those are cost without benefit.

## What to test

Test **user-visible behaviour and meaningful application behaviour**, not implementation details.

| Test this                                                                           | Not this                                         |
| ----------------------------------------------------------------------------------- | ------------------------------------------------ |
| `POST /vehicles` rejects a negative odometer with 422                               | that the handler calls `validate_odometer()`     |
| The dashboard shows an empty state with a call to action when there are no vehicles | that `useVehicles` returns `[]`                  |
| User A receives 404 requesting user B's vehicle                                     | that the query includes a `WHERE user_id` clause |
| A projection with a 6-month interval is due on the right date                       | the internal shape of the date helper            |

The heuristic: **a refactor that preserves behaviour should not break a test.** If routine
refactoring breaks tests, the tests are coupled to structure and are a liability.

## Layers

### Backend

| Layer              | Tooling                                             |
| ------------------ | --------------------------------------------------- |
| Unit / integration | pytest, pytest-asyncio, httpx ASGI transport        |
| Database           | **testcontainers Postgres** — a real database       |
| Fixtures           | factory-boy, transaction rollback per test          |
| External HTTP      | `respx` — vPIC and Resend are never called in tests |
| API contract       | `schemathesis` fuzzing the OpenAPI schema           |

**Never SQLite.** Testing against SQLite while running Postgres in production is a well-known source
of false green builds: JSONB, arrays, `ON CONFLICT`, timezone handling, constraint semantics and
transactional DDL all differ. Containers are fast enough; correctness is not negotiable for speed.

**Coverage gate: 85%**, ratcheting upward only. Lowering the gate requires a PR that explains why.

### Frontend

| Layer            | Tooling                                                   |
| ---------------- | --------------------------------------------------------- |
| Unit / component | Vitest + React Testing Library                            |
| API mocking      | MSW, with handlers typed from the generated OpenAPI types |
| End-to-end       | Playwright against `docker compose`                       |

**Coverage gate: 80%.** Query by accessible role and label (`getByRole`, `getByLabelText`) rather
than by test id — it tests the accessibility tree at the same time, for free.

Keep E2E thin: happy paths and the one or two flows whose breakage would be catastrophic. E2E tests
are the slowest and flakiest thing in any suite; they earn their place by covering integration
between systems, not by re-testing logic that a unit test already covers.

## Contract testing, concretely

```
FastAPI  →  openapi.json  →  openapi-typescript  →  packages/api-types/src/generated.ts (committed)
```

CI regenerates that file and **fails on any diff**. So a backend change that alters the contract
cannot merge without the generated types changing in the same PR — and because MSW handlers are
typed from those types, frontend mocks cannot drift from the real API either.

This is contract testing for $0 and near-zero maintenance, and it is why the monorepo is worth it.

## Required per story

Every user-scoped resource needs an **ownership test**: user A must not be able to read or mutate
user B's data. Not one test for the concept — one per resource. Broken object-level authorisation is
the most commonly shipped serious web vulnerability, and the only reliable defence is a test per
endpoint. All product queries go through the mandatory `scoped_to(user)` helper so the safe path is
the only path; the tests verify nobody bypassed it.

Every migration must be verified **up and down** in CI. Migrations follow expand/contract, so each
one is backward-compatible with the previous image — that is what makes rolling back code safe
without rolling back schema.

## Running

```bash
make check   # everything CI runs
make test    # test suites only
uv run pytest apps/api/tests/test_health.py -k ready   # one file, one case
```
