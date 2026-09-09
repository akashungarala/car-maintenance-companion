"""Write the API's OpenAPI document to a file.

Imports the app rather than calling a running server, so the contract can be
generated in CI without a database, a Redis, or a deployment. The document is
a pure function of the code, which is the property the drift check relies on.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate-openapi.py <output.json>")

    # No database or Redis URL: the contract must not depend on infrastructure
    # being reachable, or CI cannot check it.
    app = create_app(
        settings=Settings(environment="test", log_format="json"),
        readiness=ReadinessRegistry(),
    )
    # A file rather than stdout: the application logs its startup line to
    # stdout, and a generator sharing that stream emits JSON nobody can parse.
    #
    # sort_keys so the output is stable. An unordered dump would produce a diff
    # on every run and the gate would cry wolf until someone disabled it.
    Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
