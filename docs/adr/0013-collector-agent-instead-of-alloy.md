# ADR-0013: A collector DaemonSet for cluster telemetry, not Alloy

- Status: Accepted
- Date: 2026-09-08
- Supersedes: the "Grafana Alloy" choice in the Phase 0 plan (§6.1)

## Context

F8 needs three things the application cannot produce about itself:

1. container CPU and memory, to see a pod approaching its limits
2. pod state -- restart counts, phase -- for the crash-loop alert
3. pod logs, shipped and correlated with traces

The plan named Grafana Alloy for 1 and 3, which implies kube-state-metrics for
2, since Alloy scrapes state metrics but does not produce them.

That is three technologies, two configuration languages, and a second agent to
operate, on a node with 2 OCPU and 12 GB.

## Decision

Run a second OpenTelemetry Collector as a DaemonSet, using receivers already
present in the `contrib` image we deploy today:

- `kubeletstats` -> container and pod CPU/memory
- `k8s_cluster` -> pod phase and container restart counts (replaces kube-state-metrics)
- `filelog` -> pod logs

It forwards OTLP to the existing gateway collector, which remains the sole
vendor-aware egress (ADR-0004). Nothing about that boundary changes.

## Consequences

Good:

- One technology instead of three, one config language, one image to patch and
  scan. Trivy already covers it.
- Same OTLP pipeline, so the allowlist/relabel discipline in §6.2 is expressed
  once in a form we already use rather than twice in two dialects.
- The agent is separate from the gateway on purpose. Log tailing needs host
  mounts and a privileged-ish filesystem view; the gateway keeps its hardened,
  non-root, read-only-root posture and its sole-egress role.

Bad, and accepted:

- `k8s_cluster` produces a narrower set of state metrics than
  kube-state-metrics. We currently need restarts and phase, both of which it
  emits. If a future alert needs something only KSM has, we add KSM then --
  for that metric, with a reason.
- Grafana's own dashboards often assume KSM metric names, so the four
  dashboards are built against OTel semantic conventions instead of imported
  wholesale. That is work we were doing anyway, since imported dashboards
  routinely pull in far more series than the 10k free-tier cap allows.
