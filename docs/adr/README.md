# Architecture Decision Records

One file per significant decision. A decision is "significant" if reversing it would cost more
than a day, changes cost, changes the security posture, or creates vendor lock-in.

Format: **Status · Context · Decision · Consequences**. Consequences must include the bad ones —
an ADR that lists only benefits is marketing, not a record.

Superseding an ADR: write a new one and set the old one's status to `Superseded by ADR-NNNN`.
Never edit a decision's substance after it is accepted; the point is the audit trail.

| ADR                                                         | Decision                                                  | Status   |
| ----------------------------------------------------------- | --------------------------------------------------------- | -------- |
| [0001](0001-public-monorepo.md)                             | Public monorepo                                           | Accepted |
| [0002](0002-k3s-on-oracle-always-free.md)                   | k3s on Oracle Cloud Always Free                           | Accepted |
| [0003](0003-cloudnativepg-over-managed-postgres.md)         | CloudNativePG in-cluster, not managed Postgres            | Accepted |
| [0004](0004-otlp-collector-indirection.md)                  | Application emits OTLP only; Collector owns vendor config | Accepted |
| [0005](0005-modular-monolith-not-microservices.md)          | Modular monolith + one worker, not microservices          | Accepted |
| [0006](0006-own-maintenance-templates.md)                   | Own generic maintenance templates; no paid schedule API   | Accepted |
| [0007](0007-frontend-on-vercel-hobby.md)                    | Frontend on Vercel Hobby, outside the cluster             | Accepted |
| [0008](0008-argocd-pull-based-gitops.md)                    | Argo CD pull-based GitOps                                 | Accepted |
| [0009](0009-magic-link-authentication.md)                   | Magic-link authentication, no passwords                   | Accepted |
| [0010](0010-weekly-digest-email.md)                         | Weekly digest email, not per-item reminders               | Accepted |
| [0011](0011-protected-main-including-admins.md)             | `main` is protected, including for administrators         | Accepted |
| [0012](0012-served-under-a-path-on-the-portfolio-domain.md) | Served under a path on the portfolio domain               | Accepted |
