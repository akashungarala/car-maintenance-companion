"""Toolchain proof for F1.

This test exists to make the F1 pipeline meaningfully green: it proves the uv
workspace resolves, the package is importable, and pytest/coverage/mypy are
wired to real source. It is replaced by genuine behaviour tests in F2.
"""

import re

import app


def test_api_package_is_importable() -> None:
    assert app.__doc__ is not None


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", app.__version__)
