# Car Maintenance Companion — working notes for Claude

Read this first. It is the map, the conventions, and the traps. Everything else
is in `docs/`, which this file points at rather than repeats.

## What this is

A solo-founder product, built as if a small org ran it: PM, UX, frontend and
backend/infra roles, kept separate on purpose. **No QA role — engineers own
their tests. TDD is not optional.**

**The product:** every car owner is quietly forgetting something. We keep a
running, trustworthy answer to "what does my car need right now?", and ask
almost nothing to maintain it.

**The bet** (the one genuinely unvalidated thing): one odometer reading plus a
usage rate is enough to project due dates people act on — and marking an item
done silently recalibrates the rate, so the correction is free.

**Constraint:** ~$0/month. Every dependency is a free tier, and its limits are
load-bearing facts, not footnotes.

## Where things are

```
apps/api/          FastAPI + ARQ worker (one image, two entrypoints)
  src/app/identity/  magic links, sessions          docs/product/e1-identity.md
  src/app/garage/    vehicles, plans, projection    docs/product/e2..e4
  migrations/        Alembic; expand/contract only
apps/web/          Next.js 16 App Router, basePath /apps/car-maintenance-companion
packages/api-types/  generated from OpenAPI; CI fails on drift
infra/tofu/        OpenTofu: Oracle Cloud, k3s node, Cloudflare DNS
infra/k8s/         Argo CD app-of-apps, Kustomize
scripts/           cluster access, drills, Grafana provisioning
docs/adr/          14 ADRs — read before contradicting a decision
docs/ux/           UX-001..007 + committed HTML mockups
```

## Commands that matter

```bash
make check          # exactly what CI runs. Run before every commit.
make openapi        # regenerate contract types after any API change
make series-check   # Grafana cardinality gate

./scripts/cluster-access.sh     # SSH tunnel; prints the KUBECONFIG to export
./scripts/rollback-drill.sh     # timed rollback + roll-forward
./scripts/restore-drill.sh      # restore a backup into a scratch namespace
./scripts/grafana-apply.sh      # dashboards + alerts (idempotent)
./scripts/capture-secret.sh KEY # clipboard -> infra/k8s/.secrets.env, never printed
```

`kubectl` needs the tunnel: the k3s certificate covers internal IPs only and
6443 is closed at the firewall.

## How deployment works

`main` is protected (**including for admins** — ADR-0011). Everything goes
through a PR; `CI passed` is the only required check.

On merge to `main`: CI publishes arm64 images to GHCR, then the **`deploy`
branch** is updated with the image tags pinned. Argo CD tracks `deploy` for
`api`, `worker` and `web`, and `main` for platform components. GitHub cannot
grant Actions a branch-protection bypass on a personal repo, hence the separate
branch.

Argo polls every ~3 minutes. To hurry it:
`kubectl annotate app -n argocd <name> argocd.argoproj.io/refresh=hard --overwrite`

**Frontend runs in the cluster**, not on Vercel — see the trap below.

## Traps that have already cost time

**Verify the artefact, not the check.** Every serious failure here has been a
green signal measuring something adjacent to what mattered. If a check says
something shipped, confirm the shipped thing behaves — fetch the page, read the
metric, query the database.

**Vercel Hobby rate-limits _production_ deployments, silently.** Previews from
PRs keep passing while the production alias stays pinned to an older build. It
served a two-epic-old frontend for a day with everything green. Read the
signal on the _main_ commit, not the PR:
`gh api repos/OWNER/REPO/commits/SHA/status`.
The frontend moved into the cluster because of this (ADR-0007). **The portfolio
repo still proxies to it and is on the same tier**, so a repoint can stall too.

**`next/link` prepends `basePath` itself.** Internal hrefs must be
base-path relative (`/garage/add`). jsdom does not apply basePath, so a
component test asserting the full path will happily confirm a doubled prefix.
Test links by _following_ them in Playwright.

**Playwright reuses a running dev server locally** (`reuseExistingServer`), so
a stale build silently answers. Kill port 3100 before trusting a local run.

**A failed `gh pr merge` does not stop the next line.** `gh pr merge && git
checkout main` chained carelessly put edits on `main` for several minutes.

**Deploy skips are transitive.** GitHub propagates `skipped` through `needs`;
jobs gating on a matrix job that skipped will skip silently. The `deploy` job
gates on `ci-passed` and explicitly tolerates a skipped `publish`.

**mypy/ruff/eslint rules here have been right every time** they were annoying.
`setState` in an effect, refs read during render, untyped helpers — restructure
rather than suppress.

## Conventions

- **TDD, genuinely.** RED first, and when a gate is added, prove it _fails_
  before trusting that it passes. Several tests in this repo encode a
  deliberately reintroduced bug in their comments for that reason.
- **Ownership is structural.** `VehicleRepository` cannot be built without a
  user; every query is scoped by construction. Ad-hoc `WHERE user_id` is how
  IDOR ships. Every resource gets a "stranger cannot read this" test.
- **404, never 403** for someone else's record — "forbidden" confirms it exists.
- **Constraints in the database as well as Pydantic.** Validation guards one
  entry point; a constraint guards every future one.
- **Migrations are expand/contract.** The previous image must run against the
  new schema, so a rollback never needs a schema rollback.
- **Cardinality is a design constraint.** Never `user_id`, `email`, `vin`,
  `request_id` or a raw path as a metric label. Route templates only. The free
  tier is 10,000 active series and the CI gate fires at 7,000.
- **A frontend story is not Ready without a committed UX spec** in `docs/ux/`,
  covering all seven states. This is enforced on the board's `UX Ref` field.
- **Secrets never enter the transcript.** `infra/k8s/.secrets.env` (gitignored, 0600) holds them; `kubeseal` puts them in the cluster. Claude does not create
  API tokens or read them off a screen — the human does that step.

## Current state (2026-09-10)

**Done:** Phase 0 (F1–F9 + the twelve-step acceptance demo), E1 Identity, E2
Garage, E3 Projection, E4-001/002/003.

**In flight:** E4-004 (service history UI). Then E5 Reminders, E6 Learn.

**Live:** API, worker, Postgres, Redis, the whole observability stack, and the
frontend — all in the cluster. `garage.akashungarala.com` serves the current
build. `www.akashungarala.com/apps/car-maintenance-companion` will once the
portfolio's repoint deploys.

**Tracking:** GitHub Projects board #1, epics and stories both, with Status /
Area / Epic / Priority / UX Ref set. Close stories as they land.

## Open questions worth revisiting

- **Interval templates are guesses.** Oil at 5,000 mi is conservative for a
  modern car; many specify 7,500–10,000. One-line change now, data migration
  later. Worth asking the founder.
- **Recalibration uses one window** (last reading → this one), so each
  completion resets it. A reading series would be steadier. Deliberately
  deferred until there is evidence the rate is too jumpy.
- **Baseline-from-today is a product decision, not a technical one.** A car
  that genuinely needs oil today will not be told so. Recorded with its cost in
  `docs/product/e3-projection.md`.
- **CloudNativePG 1.31 removes native Barman backups** — migrate to the plugin
  before bumping.
- **Grafana trial ends ~2026-09-21**, after which 10k series is real. The
  stack's ~600 built-in Asserts rules count too.

## Working style the founder has asked for

Be critical of assumptions and say so plainly. Prefer the smallest thing that
is genuinely production-grade over architecture that looks impressive. When a
decision is a judgement call rather than a technical one — especially product
decisions with a real cost — surface it rather than quietly making it.
