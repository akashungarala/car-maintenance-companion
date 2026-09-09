# Runbook: incident triage

An alert fired in `#alerts`. This is the order to look in, and the reasoning
behind it.

## First: is it still happening?

Grafana alerts resolve themselves — a **Resolved** message means the condition
cleared. If you only see a firing message and no resolution, it is current.

Check the state directly rather than scrolling Discord:

```
kubectl get pods -n cmc
curl -s https://garage-api.akashungarala.com/ready
```

`/ready` reports each dependency separately, so it distinguishes "the API is
broken" from "Postgres is unreachable" from "Redis is unreachable" in one
request.

## Then: what changed?

Almost everything is a deploy. Check that before theorising:

```
git log --oneline origin/deploy -5
kubectl get deploy -n cmc api -o jsonpath='{.spec.template.spec.containers[0].image}'
```

If the timing lines up with a deploy, **roll back first and investigate
afterwards**. It takes about 20 seconds (measured), and a system that is
serving traffic is a much better place to debug from:

```
./scripts/rollback-drill.sh   # see deploy-and-rollback.md for the manual path
```

## Then: follow one request through

The whole point of F8 is that a single request is traceable end to end. Do not
read logs in aggregate — find one failing request and follow it:

1. **CMC · Service health** shows which status code and which route
2. Open the log line for a failing request; every line carries `trace_id`
3. That `trace_id` opens the trace in Tempo, showing `api → postgres` spans
4. The slow or failing span is the answer

A background job failure works the same way: the job span is linked to the
enqueue that caused it, so "why was this job slow" is answerable from the
schedule that triggered it.

## Alert-specific first moves

| Alert                  | Look at                                                                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API is down            | `kubectl get pods -n cmc`, then events. Usually a failed image pull or a crash on startup.                                                                  |
| Error rate above 5%    | Service health dashboard → which route, which status. Then one trace.                                                                                       |
| p95 latency above 1.5s | **CMC · Database** first: connection saturation and long transactions cause more latency than application code does.                                        |
| Container restart loop | `kubectl describe pod`, then `kubectl logs --previous`. A container exiting **0** in a loop also counts — that failure reads as healthy everywhere else.    |
| Database unreachable   | `kubectl get cluster -n cmc cmc-db`, CNPG operator logs. Every database panel is stale, not healthy, while this fires.                                      |
| Backup is stale        | [database-restore.md](database-restore.md). Check whether backups are failing rather than simply absent.                                                    |
| Queue is backing up    | Is the worker running and consuming? Queue depth is reported by the CronJob, so it keeps being reported when the worker is dead — which is the usual cause. |

## When the monitoring is the problem

Telemetry failures look exactly like quiet:

```
kubectl logs -n cmc deploy/otel-collector --tail=50
kubectl port-forward -n cmc deploy/otel-collector 8888:8888
curl -s localhost:8888/metrics | grep -E 'otelcol_exporter_(sent|send_failed)'
```

`send_failed` climbing means data is not reaching Grafana and the dashboards
are stale rather than calm. Zero spans at idle is **correct** — probe traffic
and Redis polling are deliberately filtered.

## Escalation

There is one engineer. "Escalation" means deciding whether to keep debugging or
to stop the bleeding: roll back, scale down the worker, or turn off rate
limiting (`CMC_RATE_LIMIT_ENABLED=false`) if the limiter itself is implicated.
Prefer the reversible action, then investigate with the system stable.
