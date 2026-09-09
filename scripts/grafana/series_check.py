"""Fail if active series approach the free-tier cap.

Grafana Cloud allows 10,000 active series. The gate is 7,000, leaving room to
notice and react rather than discovering the limit as silently dropped metrics
-- which is how it actually presents: no error, no alert, just dashboards that
quietly stop being right.

Checked against production rather than in a pull request. A PR cannot change
cardinality until it is deployed, and the number that matters is the one the
running system is producing.
"""

import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("GRAFANA_URL", "https://eagerginger3042.grafana.net")
TOKEN = os.environ.get("GRAFANA_API_TOKEN", "")
LIMIT = int(os.environ.get("SERIES_LIMIT", "7000"))
CAP = 10_000


def query(datasource: str, expr: str) -> list[dict]:
    url = f"{BASE}/api/datasources/proxy/uid/{datasource}/api/v1/query?" + urllib.parse.urlencode(
        {"query": expr}
    )
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode()).get("data", {}).get("result", [])


def main() -> int:
    if not TOKEN:
        print("GRAFANA_API_TOKEN is not set")
        return 2

    result = query("grafanacloud-usage", "grafanacloud_instance_active_series")
    if not result:
        # Not a pass. An unavailable number is an unchecked gate, and a gate
        # that silently passes when it cannot run is not a gate.
        print("could not read active series from the usage datasource")
        return 2

    active = float(result[0]["value"][1])
    print(f"active series: {active:.0f}  (gate {LIMIT}, cap {CAP})")

    breakdown = query(
        "grafanacloud-prom",
        'count by (__name__) ({__name__=~"http_.+|job_.+|queue_.+|k8s_.+|cnpg_.+"})',
    )
    ranked = sorted(breakdown, key=lambda r: -int(r["value"][1]))
    print("largest contributors:")
    for row in ranked[:10]:
        print(f"  {row['metric']['__name__']:<50} {row['value'][1]:>6}")

    if active > LIMIT:
        print(
            f"\nFAIL: {active:.0f} active series exceeds the {LIMIT} gate.\n"
            "Above 10,000 Grafana drops the overflow without erroring, so the\n"
            "symptom is dashboards that are subtly wrong rather than an outage.\n"
            "Look for a new label carrying an unbounded value -- an id, a path,\n"
            "an email -- rather than for more metrics."
        )
        return 1

    print(f"\nOK: {LIMIT - active:.0f} series of headroom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
