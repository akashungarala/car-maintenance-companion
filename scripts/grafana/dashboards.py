"""The four dashboards, as code.

Defined here rather than as committed JSON so there is one source of truth. A
dashboard edited in the Grafana UI is overwritten on the next apply, which is
deliberate: a dashboard nobody can reproduce from the repository is a dashboard
that disappears with the account.

Each dashboard answers a named question. Panels that answer no question were
left out -- an unused panel still costs a query on every refresh, and a wall of
graphs is how people stop reading dashboards.
"""

from typing import Any

PROM = {"type": "prometheus", "uid": "grafanacloud-prom"}


def _panel(
    title: str,
    kind: str,
    targets: list[dict[str, str]],
    grid: tuple[int, int, int, int],
    unit: str | None = None,
    description: str = "",
    thresholds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    w, h, x, y = grid
    defaults: dict[str, Any] = {"custom": {}}
    if unit:
        defaults["unit"] = unit
    if thresholds:
        defaults["thresholds"] = {"mode": "absolute", "steps": thresholds}
        defaults["color"] = {"mode": "thresholds"}
    return {
        "type": kind,
        "title": title,
        "description": description,
        "datasource": PROM,
        "gridPos": {"w": w, "h": h, "x": x, "y": y},
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "targets": [{"refId": chr(65 + i), "datasource": PROM, **t} for i, t in enumerate(targets)],
        "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}},
    }


def _text(title: str, content: str, grid: tuple[int, int, int, int]) -> dict[str, Any]:
    w, h, x, y = grid
    return {
        "type": "text",
        "title": title,
        "gridPos": {"w": w, "h": h, "x": x, "y": y},
        "options": {"mode": "markdown", "content": content},
    }


def _dashboard(
    uid: str, title: str, description: str, panels: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "uid": uid,
        "title": title,
        "description": description,
        "tags": ["cmc"],
        "timezone": "browser",
        "schemaVersion": 39,
        "refresh": "1m",
        "time": {"from": "now-6h", "to": "now"},
        "panels": panels,
        "editable": True,
    }


OK_WARN_BAD = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 1},
    {"color": "red", "value": 5},
]


def service_health() -> dict[str, Any]:
    """Is it up, is it failing, is it slow, and which route."""
    return _dashboard(
        "cmc-service-health",
        "CMC · Service health",
        "Is it healthy, is it getting slower, which endpoint, did the deploy break it.",
        [
            _panel(
                "Requests/sec",
                "stat",
                [{"expr": 'sum(rate(http_server_duration_milliseconds_count{job="cmc-api"}[5m]))'}],
                (6, 4, 0, 0),
                unit="reqps",
            ),
            _panel(
                "Error rate",
                "stat",
                [
                    {
                        "expr": (
                            "sum(rate(http_server_duration_milliseconds_count"
                            '{job="cmc-api",http_status_code=~"5.."}[5m]))'
                            " / clamp_min(sum(rate(http_server_duration_milliseconds_count"
                            '{job="cmc-api"}[5m])), 0.001)'
                        )
                    }
                ],
                (6, 4, 6, 0),
                unit="percentunit",
                description="clamp_min avoids dividing by zero when there is no traffic, which "
                "would render as a spike to infinity rather than as 'no requests'.",
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 0.05},
                ],
            ),
            _panel(
                "In flight",
                "stat",
                [{"expr": 'sum(http_server_active_requests{job="cmc-api"})'}],
                (6, 4, 12, 0),
            ),
            _panel(
                "p95 latency",
                "stat",
                [
                    {
                        "expr": (
                            "histogram_quantile(0.95, sum by (le) ("
                            'rate(http_server_duration_milliseconds_bucket{job="cmc-api"}[5m])))'
                        )
                    }
                ],
                (6, 4, 18, 0),
                unit="ms",
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 1500},
                ],
            ),
            _panel(
                "Latency percentiles",
                "timeseries",
                [
                    {
                        "expr": (
                            "histogram_quantile(0.95, sum by (le) ("
                            'rate(http_server_duration_milliseconds_bucket{job="cmc-api"}[5m])))'
                        ),
                        "legendFormat": "p95",
                    },
                    {
                        "expr": (
                            "histogram_quantile(0.50, sum by (le) ("
                            'rate(http_server_duration_milliseconds_bucket{job="cmc-api"}[5m])))'
                        ),
                        "legendFormat": "p50",
                    },
                ],
                (12, 8, 0, 4),
                unit="ms",
            ),
            _panel(
                "Requests by status",
                "timeseries",
                [
                    {
                        "expr": (
                            "sum by (http_status_code) ("
                            'rate(http_server_duration_milliseconds_count{job="cmc-api"}[5m]))'
                        ),
                        "legendFormat": "{{http_status_code}}",
                    }
                ],
                (12, 8, 12, 4),
                unit="reqps",
            ),
            _panel(
                "Slowest routes (p95)",
                "timeseries",
                [
                    {
                        "expr": (
                            "histogram_quantile(0.95, sum by (le, http_target) ("
                            'rate(http_server_duration_milliseconds_bucket{job="cmc-api"}[5m])))'
                        ),
                        "legendFormat": "{{http_target}}",
                    }
                ],
                (24, 8, 0, 12),
                unit="ms",
                description="Empty until product routes exist. Phase 0 serves only /health and "
                "/ready, both excluded from instrumentation, so every request so far is a 404 "
                "and carries no route template.",
            ),
        ],
    )


def infrastructure() -> dict[str, Any]:
    """Is the cluster healthy, and is anything near the limit that will kill it."""
    return _dashboard(
        "cmc-infrastructure",
        "CMC · Infrastructure",
        "Pod availability, restarts, and usage against the limits that cause "
        "throttling and OOM kills.",
        [
            _panel(
                "Container restarts (1h)",
                "stat",
                [{"expr": 'sum(increase(k8s_container_restarts{k8s_namespace_name="cmc"}[1h]))'}],
                (6, 4, 0, 0),
                thresholds=OK_WARN_BAD,
                description="A container that exits 0 in a loop is still restarting. This counts "
                "those too, which is how the collector's 107 silent restarts were missed.",
            ),
            _panel(
                "Node ready",
                "stat",
                [{"expr": "min(k8s_node_condition_ready)"}],
                (6, 4, 6, 0),
            ),
            _panel(
                "Deployments below desired",
                "stat",
                [
                    {
                        "expr": (
                            'sum(k8s_deployment_desired{k8s_namespace_name="cmc"})'
                            ' - sum(k8s_deployment_available{k8s_namespace_name="cmc"})'
                        )
                    }
                ],
                (6, 4, 12, 0),
                thresholds=OK_WARN_BAD,
            ),
            _panel(
                "Node memory",
                "stat",
                [{"expr": "max(k8s_node_memory_working_set_bytes)"}],
                (6, 4, 18, 0),
                unit="bytes",
            ),
            _panel(
                "Memory against limit",
                "timeseries",
                [
                    {
                        "expr": (
                            "max by (k8s_container_name) ("
                            'k8s_container_memory_limit_utilization_ratio{k8s_namespace_name="cmc"})'
                        ),
                        "legendFormat": "{{k8s_container_name}}",
                    }
                ],
                (12, 8, 0, 4),
                unit="percentunit",
                description="Ratio of the limit, not raw bytes. Raw usage cannot answer whether a "
                "container is about to be OOM-killed without also knowing its limit.",
            ),
            _panel(
                "Pod CPU usage",
                "timeseries",
                [
                    {
                        "expr": 'k8s_pod_cpu_usage{k8s_namespace_name="cmc"}',
                        "legendFormat": "{{k8s_pod_name}}",
                    }
                ],
                (12, 8, 12, 4),
                unit="cores",
                description="Usage, not utilisation-against-limit, because no container here "
                "sets a CPU limit. That is deliberate: a CPU limit causes throttling rather "
                "than eviction, so it degrades latency invisibly instead of failing loudly. "
                "Memory limits are set, and memory is what actually kills a container.",
            ),
            _panel(
                "Pod memory",
                "timeseries",
                [
                    {
                        "expr": 'k8s_pod_memory_working_set_bytes{k8s_namespace_name="cmc"}',
                        "legendFormat": "{{k8s_pod_name}}",
                    }
                ],
                (24, 8, 0, 12),
                unit="bytes",
            ),
        ],
    )


def database() -> dict[str, Any]:
    """Is Postgres healthy, and does a restorable backup actually exist."""
    return _dashboard(
        "cmc-database",
        "CMC · Database",
        "Connections, size, and the age of the most recent backup.",
        [
            _panel(
                "Backup age",
                "stat",
                [{"expr": "time() - max(cnpg_collector_last_available_backup_timestamp)"}],
                (8, 4, 0, 0),
                unit="s",
                description="The single most important number here. A backup system nobody "
                "measures is indistinguishable from one that stopped working months ago.",
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 93600},
                ],
            ),
            _panel(
                "Exporter up",
                "stat",
                [{"expr": "min(cnpg_collector_up)"}],
                (8, 4, 8, 0),
                description="Zero means every other panel here is stale rather than healthy.",
            ),
            _panel(
                "Database size",
                "stat",
                [{"expr": 'max(cnpg_pg_database_size_bytes{datname="cmc"})'}],
                (8, 4, 16, 0),
                unit="bytes",
            ),
            _panel(
                "Connections by state",
                "timeseries",
                [
                    {
                        "expr": "sum by (state) (cnpg_backends_total)",
                        "legendFormat": "{{state}}",
                    }
                ],
                (12, 8, 0, 4),
            ),
            _panel(
                "Longest transaction",
                "timeseries",
                [{"expr": "max(cnpg_backends_max_tx_duration_seconds)", "legendFormat": "max"}],
                (12, 8, 12, 4),
                unit="s",
                description="A long-running transaction blocks vacuum and holds locks. It is "
                "usually the first visible symptom of a job that forgot to commit.",
            ),
            _panel(
                "Origin certificate: days remaining",
                "stat",
                [
                    {
                        "expr": "(min(certmanager_certificate_expiration_timestamp_seconds) "
                        "- time()) / 86400"
                    }
                ],
                (24, 4, 0, 12),
                unit="d",
                description="The zone is on Full (strict), so Cloudflare verifies this "
                "certificate on every connection. Expiry is not a degradation -- Cloudflare "
                "returns 526 and stops proxying entirely. cert-manager renews at 30 days.",
                thresholds=[
                    {"color": "red", "value": None},
                    {"color": "yellow", "value": 14},
                    {"color": "green", "value": 25},
                ],
            ),
            _panel(
                "WAL archive failures",
                "timeseries",
                [
                    {
                        "expr": "increase(cnpg_pg_stat_archiver_failed_count_total[1h])",
                        "legendFormat": "failures/hour",
                    }
                ],
                (24, 6, 0, 16),
                description="WAL archiving is what makes point-in-time recovery possible. "
                "Failures here mean the backup is quietly becoming less recoverable.",
            ),
        ],
    )


def async_work() -> dict[str, Any]:
    """Is work piling up, how long does it take, is anything giving up."""
    return _dashboard(
        "cmc-async",
        "CMC · Async",
        "Queue depth, job latency and failures.",
        [
            _panel(
                "Queue depth",
                "stat",
                [{"expr": "max(queue_depth)"}],
                (8, 4, 0, 0),
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "red", "value": 100},
                ],
                description="Reported by the CronJob, which keeps running when the worker is "
                "down -- which is exactly when a rising queue matters.",
            ),
            _panel(
                "Job p95",
                "stat",
                [
                    {
                        "expr": (
                            "histogram_quantile(0.95, sum by (le) ("
                            "rate(job_duration_milliseconds_bucket[15m])))"
                        )
                    }
                ],
                (8, 4, 8, 0),
                unit="ms",
            ),
            _panel(
                "Dead letters (24h)",
                "stat",
                [{"expr": "sum(increase(job_dead_letters_total[24h])) or vector(0)"}],
                (8, 4, 16, 0),
                thresholds=OK_WARN_BAD,
                description="`or vector(0)` because a counter that has never incremented does "
                "not exist as a series, and an empty panel reads as broken rather than as good "
                "news.",
            ),
            _panel(
                "Queue depth over time",
                "timeseries",
                [{"expr": "max(queue_depth)", "legendFormat": "waiting"}],
                (12, 8, 0, 4),
            ),
            _panel(
                "Jobs by outcome",
                "timeseries",
                [
                    {
                        "expr": "sum by (outcome) (rate(job_duration_milliseconds_count[5m]))",
                        "legendFormat": "{{outcome}}",
                    }
                ],
                (12, 8, 12, 4),
                unit="reqps",
            ),
            _panel(
                "Emails sent today, by kind",
                "timeseries",
                [
                    {
                        "expr": "sum by (kind) (increase(email_sent_total[24h]))",
                        "legendFormat": "{{kind}}",
                    }
                ],
                (24, 6, 0, 12),
                description="The free tier allows 100 a day, shared between sign-in links and "
                "the weekly digest. Running out is invisible until someone cannot sign in.",
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 70},
                    {"color": "red", "value": 95},
                ],
            ),
            _panel(
                "Job latency percentiles",
                "timeseries",
                [
                    {
                        "expr": (
                            "histogram_quantile(0.95, sum by (le) ("
                            "rate(job_duration_milliseconds_bucket[15m])))"
                        ),
                        "legendFormat": "p95",
                    },
                    {
                        "expr": (
                            "histogram_quantile(0.50, sum by (le) ("
                            "rate(job_duration_milliseconds_bucket[15m])))"
                        ),
                        "legendFormat": "p50",
                    },
                ],
                (24, 8, 0, 18),
                unit="ms",
            ),
        ],
    )


ALL = [service_health, infrastructure, database, async_work]
