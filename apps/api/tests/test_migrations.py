"""Migrations must apply and reverse cleanly.

Every migration is verified in both directions. Migrations follow
expand/contract, so each one stays backward-compatible with the previous image
— that is what makes rolling back code safe without rolling back schema
(docs/runbook/deploy-and-rollback.md).
"""

import asyncio
import pathlib

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.database import Database

pytestmark = pytest.mark.integration

API_ROOT = pathlib.Path(__file__).resolve().parents[1]


async def _alembic(cfg: Config, action: str, target: str) -> None:
    """Run an Alembic command off the test's event loop.

    migrations/env.py calls asyncio.run(), which cannot nest inside the loop
    pytest-asyncio is already running. A worker thread gets its own loop.
    """
    fn = command.upgrade if action == "upgrade" else command.downgrade
    await asyncio.to_thread(fn, cfg, target)


def _config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


async def test_upgrade_then_downgrade_round_trips(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMC_DATABASE_URL", postgres_url)
    cfg = _config(postgres_url)
    # Verified with the same async driver production uses, rather than pulling
    # in a second, sync driver purely for tests.
    db = Database(postgres_url)

    await _alembic(cfg, "upgrade", "head")
    applied = await db.execute_scalar("SELECT version_num FROM alembic_version")
    assert applied is not None, "upgrade left no version recorded"

    await _alembic(cfg, "downgrade", "base")
    remaining = await db.execute_scalar("SELECT count(*) FROM alembic_version")
    assert remaining == 0, "downgrade did not unwind to base"

    # Leave the database at head so later tests see a migrated schema.
    await _alembic(cfg, "upgrade", "head")
    await db.dispose()


async def test_alembic_version_table_exists_after_upgrade(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMC_DATABASE_URL", postgres_url)
    await _alembic(_config(postgres_url), "upgrade", "head")
    db = Database(postgres_url)

    present = await db.execute_scalar("SELECT to_regclass('public.alembic_version') IS NOT NULL")

    assert present is True
    await db.dispose()


def test_there_is_exactly_one_head() -> None:
    """Two heads mean two branches of history and an ambiguous `upgrade head`.

    It happens when two branches each add a migration and both merge, and it is
    far cheaper to catch here than during a deploy.
    """
    script = ScriptDirectory(str(API_ROOT / "migrations"))

    assert len(script.get_heads()) == 1, f"expected one head, found {script.get_heads()}"


def test_every_revision_is_reachable_from_head() -> None:
    """A revision orphaned from the chain never runs and is silently dead."""
    script = ScriptDirectory(str(API_ROOT / "migrations"))
    head = script.get_current_head()

    reachable = {rev.revision for rev in script.iterate_revisions(head, "base")}
    on_disk = {rev.revision for rev in script.walk_revisions()}

    assert on_disk == reachable, f"unreachable revisions: {on_disk - reachable}"
