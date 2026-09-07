# ADR-0004: Application emits OTLP only; the Collector owns vendor config

**Status:** Accepted · 2026-09-07

## Context

We need metrics, logs and traces from day one, and we intend to use Grafana Cloud's free tier
(10k active series, 50 GB logs, 50 GB traces, 14-day retention, no credit card). Free observability
tiers are exactly the kind of thing that changes terms, and 14-day retention may eventually be
insufficient.

The tempting shortcut is to configure vendor exporters directly in the application SDK.

## Decision

Application code emits **OTLP and nothing else**, to a local OpenTelemetry Collector. The Collector
is the sole component that knows a vendor exists. Grafana Alloy handles Kubernetes infrastructure
metrics and pod log tailing.

## Consequences

**Good:** swapping Grafana Cloud for self-hosted Loki/Tempo/Mimir — or anything else speaking OTLP —
is a Collector exporter change with **zero application code changes**. The Collector is also the
right place to enforce cardinality limits, redact sensitive attributes, batch, and buffer during
backend outages.

**Bad:** one more component to run and monitor. If the Collector is down, telemetry is lost — so it
runs as a DaemonSet with its own liveness probe, and "no telemetry received" is itself an alert
condition.

**Reversal cost:** trivial — this decision exists specifically to keep reversal cost near zero.
