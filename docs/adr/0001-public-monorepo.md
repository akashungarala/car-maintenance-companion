# ADR-0001: Public monorepo

**Status:** Accepted · 2026-09-07

## Context

Frontend, backend, worker, shared API types, Kubernetes manifests and infrastructure code all need
to change together. A backend contract change and its frontend consumer should land in one atomic
commit, or the contract check is meaningless.

Separately, the production cluster runs on **arm64** (Oracle Ampere). Building arm64 images under
QEMU emulation on x86 runners is roughly 5-10x slower. GitHub provides native `ubuntu-24.04-arm`
runners free and unmetered on **public** repositories; on private repositories they are available
but consume the 2,000 minute/month allowance.

## Decision

A single **public** monorepo containing `apps/`, `packages/`, `infra/` and `docs/`.

## Consequences

**Good:** atomic cross-stack changes; one CI pipeline; unlimited Actions minutes; free native arm64
builders; free unlimited GitHub Projects; Argo CD watches exactly one repo.

**Bad:** all code is publicly visible, so secrets discipline is not optional — `gitleaks` runs in
pre-commit and CI, and every production secret is a Sealed Secret or a GitHub Actions secret.
Security-through-obscurity is unavailable to us, which is the correct posture anyway but means
authorisation bugs are exploitable the moment they ship.

**Reversal cost:** low today (make the repo private, accept the minute cap and metered ARM
runners); it rises once there is public traffic or forks.
