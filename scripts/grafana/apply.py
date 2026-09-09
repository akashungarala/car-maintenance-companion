"""Apply dashboards, alerts and the Discord contact point to Grafana Cloud.

Idempotent: run it as often as you like. Dashboards are upserted by uid and
alert rules by a uid derived from their title, so re-running updates in place
rather than accumulating duplicates.

Reads GRAFANA_API_TOKEN and DISCORD_WEBHOOK_URL from the environment. Neither
is ever printed.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import alerts
import dashboards

BASE = os.environ.get("GRAFANA_URL", "https://eagerginger3042.grafana.net")
TOKEN = os.environ.get("GRAFANA_API_TOKEN", "")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
FOLDER_TITLE = "Car Maintenance Companion"
FOLDER_UID = "cmc"
RULE_GROUP = "cmc"


def call(method: str, path: str, body: object = None, ok: tuple[int, ...] = (200, 201, 202)):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    request.add_header("Authorization", f"Bearer {TOKEN}")
    request.add_header("Content-Type", "application/json")
    # Without this, provisioned rules are read-only in the UI. They should stay
    # editable: an alert you cannot silence or tweak during an incident is an
    # alert you end up deleting.
    request.add_header("X-Disable-Provenance", "true")
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        if error.code in ok:
            return error.code, None
        return error.code, raw


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def ensure_folder() -> None:
    status, _ = call("POST", "/api/folders", {"uid": FOLDER_UID, "title": FOLDER_TITLE})
    if status in (200, 201):
        print(f"  folder created: {FOLDER_TITLE}")
    elif status in (409, 412):
        print(f"  folder exists: {FOLDER_TITLE}")
    else:
        raise SystemExit(f"  could not create folder: {status}")


def apply_dashboards() -> None:
    for build in dashboards.ALL:
        board = build()
        status, body = call(
            "POST",
            "/api/dashboards/db",
            {"dashboard": board, "folderUid": FOLDER_UID, "overwrite": True},
        )
        if status != 200:
            raise SystemExit(f"  dashboard {board['uid']} failed: {status} {body}")
        print(f"  dashboard applied: {board['title']}")


def apply_contact_point() -> None:
    if not WEBHOOK:
        raise SystemExit("  DISCORD_WEBHOOK_URL is not set")
    status, existing = call("GET", "/api/v1/provisioning/contact-points")
    point = {
        "name": "discord",
        "type": "discord",
        "settings": {"url": WEBHOOK},
        "disableResolveMessage": False,
    }
    found = [c for c in (existing or []) if c.get("name") == "discord"]
    if found:
        uid = found[0]["uid"]
        status, body = call(
            "PUT", f"/api/v1/provisioning/contact-points/{uid}", {**point, "uid": uid}
        )
        print(
            "  contact point updated: discord"
            if status in (200, 202)
            else f"  FAILED {status} {body}"
        )
    else:
        status, body = call("POST", "/api/v1/provisioning/contact-points", point)
        print(
            "  contact point created: discord"
            if status in (200, 201, 202)
            else f"  FAILED {status} {body}"
        )


def apply_route() -> None:
    """Route this service's alerts to Discord without touching anything else.

    A child route rather than changing the root receiver: the root is shared
    with whatever else the stack notifies, and silently redirecting all of it
    is not ours to do.
    """
    status, policy = call("GET", "/api/v1/provisioning/policies")
    if status != 200 or not isinstance(policy, dict):
        raise SystemExit(f"  could not read notification policy: {status}")
    routes = [r for r in policy.get("routes", []) if r.get("receiver") != "discord"]
    routes.append(
        {
            "receiver": "discord",
            "object_matchers": [["service", "=", "cmc"]],
            "group_by": ["alertname"],
            "group_wait": "30s",
            "group_interval": "5m",
            # Re-notify daily, not hourly. An unresolved warning repeating every
            # hour is how a channel becomes unreadable.
            "repeat_interval": "24h",
        }
    )
    policy["routes"] = routes
    status, body = call("PUT", "/api/v1/provisioning/policies", policy)
    print("  notification route applied" if status in (200, 202) else f"  FAILED {status} {body}")


def apply_alerts() -> None:
    status, existing = call("GET", "/api/v1/provisioning/alert-rules")
    by_uid = {r["uid"]: r for r in (existing or []) if isinstance(r, dict) and "uid" in r}
    for rule in alerts.rules():
        uid = f"cmc-{slug(rule['title'])}"
        payload = {**rule, "uid": uid, "folderUID": FOLDER_UID, "ruleGroup": RULE_GROUP, "orgID": 1}
        if uid in by_uid:
            status, body = call("PUT", f"/api/v1/provisioning/alert-rules/{uid}", payload)
            verb = "updated"
        else:
            status, body = call("POST", "/api/v1/provisioning/alert-rules", payload)
            verb = "created"
        if status not in (200, 201, 202):
            raise SystemExit(f"  alert {rule['title']!r} failed: {status} {body}")
        print(f"  alert {verb}: [{rule['labels']['severity']}] {rule['title']}")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("GRAFANA_API_TOKEN is not set")
    ensure_folder()
    apply_dashboards()
    apply_contact_point()
    apply_route()
    apply_alerts()
    print("  done")
