"""The uvicorn entrypoint.

Cheap, but it catches a whole class of failure that unit tests miss: an app
that works under the test factory yet cannot be imported the way the container
imports it. That failure otherwise surfaces as a crash-looping pod.
"""


def test_asgi_module_exposes_an_application() -> None:
    from app.asgi import app

    assert app.title == "Car Maintenance Companion API"
    # Assert against the published contract rather than the router internals.
    assert {"/health", "/ready"} <= set(app.openapi()["paths"])
