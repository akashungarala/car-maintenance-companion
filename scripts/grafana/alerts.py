"""The seven alerts.

Every one is actionable: it names something a person would get up and do
something about. Alerts that fire and are routinely ignored train you to ignore
the ones that matter, so a rule that cannot be acted on does not belong here.

Severity splits into `page` (something is broken now) and `warn` (something
will be broken soon). Both go to Discord; the distinction is for the reader at
2am deciding whether to open a laptop.
"""

from typing import Any

PROM = "grafanacloud-prom"


def _rule(
    title: str,
    expr: str,
    threshold: float,
    *,
    op: str,
    for_: str,
    severity: str,
    summary: str,
    runbook: str,
    lookback: int = 600,
) -> dict[str, Any]:
    """One alert: an instant query, reduced to a number, compared to a threshold."""
    return {
        "title": title,
        "condition": "C",
        "data": [
            {
                "refId": "A",
                "relativeTimeRange": {"from": lookback, "to": 0},
                "datasourceUid": PROM,
                "model": {
                    "refId": "A",
                    "expr": expr,
                    "instant": True,
                    "datasource": {"type": "prometheus", "uid": PROM},
                },
            },
            {
                "refId": "C",
                "datasourceUid": "__expr__",
                "model": {
                    "refId": "C",
                    "type": "threshold",
                    "expression": "A",
                    "datasource": {"type": "__expr__", "uid": "__expr__"},
                    "conditions": [
                        {
                            "evaluator": {"type": op, "params": [threshold]},
                            "operator": {"type": "and"},
                            "query": {"params": ["A"]},
                            "reducer": {"type": "last", "params": []},
                            "type": "query",
                        }
                    ],
                },
            },
        ],
        # NoData is OK, not Alerting. These queries return nothing when the
        # system is idle, and an alert that fires every quiet night is an alert
        # that gets muted.
        "noDataState": "OK",
        "execErrState": "Error",
        "for": for_,
        "labels": {"severity": severity, "service": "cmc"},
        "annotations": {"summary": summary, "runbook": runbook},
    }


def rules() -> list[dict[str, Any]]:
    return [
        _rule(
            "API is down",
            'sum(k8s_deployment_available{k8s_namespace_name="cmc",k8s_deployment_name="api"})',
            1,
            op="lt",
            for_="3m",
            severity="page",
            summary="No API pods are available. The site is down.",
            runbook="kubectl get pods -n cmc; check events and the most recent deploy. "
            "Roll back by reverting the tag bump on the deploy branch.",
        ),
        _rule(
            "Error rate above 5%",
            "sum(rate(http_server_duration_milliseconds_count"
            '{job="cmc-api",http_status_code=~"5.."}[5m]))'
            " / clamp_min(sum(rate(http_server_duration_milliseconds_count"
            '{job="cmc-api"}[5m])), 0.001)',
            0.05,
            op="gt",
            for_="5m",
            severity="page",
            summary="More than 5% of requests are returning 5xx.",
            runbook="Open CMC · Service health, find the failing status code and route, then "
            "follow a trace_id from the logs into Tempo.",
        ),
        _rule(
            "p95 latency above 1.5s",
            "histogram_quantile(0.95, sum by (le) ("
            'rate(http_server_duration_milliseconds_bucket{job="cmc-api"}[10m])))',
            1500,
            op="gt",
            for_="10m",
            severity="warn",
            summary="p95 request latency is above 1.5s.",
            runbook="Check CMC · Database for connection saturation or a long-running "
            "transaction before assuming the application is at fault.",
        ),
        _rule(
            "Container restart loop",
            'sum(increase(k8s_container_restarts{k8s_namespace_name="cmc"}[15m]))',
            3,
            op="gt",
            for_="5m",
            severity="page",
            summary="A container has restarted more than three times in fifteen minutes.",
            runbook="kubectl describe pod, then kubectl logs --previous. Note that a container "
            "exiting 0 in a loop also counts here -- that is how the collector's silent restart "
            "loop stayed invisible for 17 hours.",
        ),
        _rule(
            "Database unreachable",
            "min(cnpg_collector_up)",
            1,
            op="lt",
            for_="2m",
            severity="page",
            summary="The Postgres exporter cannot reach the database.",
            runbook="kubectl get cluster -n cmc cmc-db; check CloudNativePG operator logs. "
            "Every other panel on the database dashboard is stale while this is firing.",
        ),
        _rule(
            "Backup is stale",
            "time() - max(cnpg_collector_last_available_backup_timestamp)",
            93600,  # 26 hours: a daily backup with two hours of slack.
            op="gt",
            for_="30m",
            severity="warn",
            summary="No successful database backup in the last 26 hours.",
            runbook="kubectl get backups -n cmc; check the object storage credentials and the "
            "barman sidecar logs. Run scripts/restore-drill.sh once fixed -- a backup that has "
            "never been restored is not a backup.",
        ),
        _rule(
            "Queue is backing up",
            "max(queue_depth)",
            100,
            op="gt",
            for_="15m",
            severity="warn",
            summary="More than 100 jobs are waiting to be processed.",
            runbook="Check the worker is running and consuming: kubectl logs -n cmc deploy/worker. "
            "Queue depth is reported by the CronJob, so this keeps working when the worker is not.",
        ),
    ]
