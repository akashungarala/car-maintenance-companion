# Web

Next.js frontend. Phase 0 ships a single Hello World page — the product starts at E1.

```bash
pnpm --filter @cmc/web dev        # http://localhost:3000
pnpm --filter @cmc/web test       # Vitest + coverage (gate: 80%)
pnpm --filter @cmc/web e2e        # Playwright against a real production build
```

## Deliberately pinned below latest

Two dependencies are **intentionally not on the newest version**. Upgrading them breaks the
pipeline, so please read this before bumping.

| Package    | Pinned | Latest | Why                                                                                                                                                                                                        |
| ---------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TypeScript | 6.0.3  | 7.0.2  | `typescript-eslint` does not support TS 7 ([#10940](https://github.com/typescript-eslint/typescript-eslint/issues/10940)). With TS 7, ESLint fails to start entirely.                                      |
| ESLint     | 9.39.5 | 10.x   | `eslint-plugin-react`, pulled in by `eslint-config-next`, still uses the ESLint 9 rule-context API and throws `contextOrFilename.getFilename is not a function` on 10. Next's own peer range is `>=9.0.0`. |

Both are ecosystem lag rather than anything about this codebase. The trade was made deliberately:
linting is a required gate, and losing it to run a newer compiler is the wrong direction. Revisit
when the upstream issues close — Dependabot will keep proposing the bumps, and they should be
rejected until then.

## Testing

Unit and component tests use Vitest + React Testing Library, querying by accessible role and label
so the accessibility tree is exercised for free. MSW is wired with `onUnhandledRequest: 'error'`,
so any accidental real network call from a test fails loudly rather than producing a slow,
non-deterministic suite.

Playwright runs against the **standalone production build**, not the dev server — dev-only
behaviour (unminified output, relaxed headers) would mean the tests prove something other than what
ships. The suite asserts the security headers directly, because header regressions are silent.

## Container

`Dockerfile` builds the standalone output and runs it as a non-root user. The frontend deploys to
Vercel today (ADR-0007); this image exists so that moving into the Kubernetes cluster is a config
change rather than a rewrite, and it is built and smoke-tested in CI on every change so it cannot
rot while unused.

Note that `output: 'standalone'` does **not** include static assets — they are copied separately in
both the Dockerfile and the Playwright web server command. Forgetting that produces a page that
renders with every asset 404ing, which looks like a broken deploy rather than a missing copy step.
