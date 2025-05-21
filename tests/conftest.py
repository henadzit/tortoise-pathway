import os
from pathlib import Path
from typing import AsyncGenerator

import pytest

from tortoise import Tortoise
from tortoise.backends.base.config_generator import expand_db_url


@pytest.fixture(autouse=True)
async def clean_apps():
    """Clean up Tortoise apps after tests."""
    Tortoise.apps = {}


@pytest.fixture
async def setup_db_file(tmp_path: Path) -> AsyncGenerator[Path, None]:
    """Create a temporary SQLite database file."""
    db_path = tmp_path / "test_db.sqlite3"

    if db_path.exists():
        db_path.unlink()

    yield db_path

    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def tortoise_config(setup_db_file):
    db_url = os.environ.get("TORTOISE_TEST_DB", f"sqlite://{setup_db_file}")

    return {
        "connections": {
            "default": expand_db_url(db_url, testing=True),
        },
        "apps": {
            "test": {
                "models": ["tests.models"],
                "default_connection": "default",
            },
            "tortoise_pathway": {
                "models": ["tortoise_pathway.models"],
                "default_connection": "default",
            },
        },
    }


@pytest.fixture
async def setup_test_db(tortoise_config):
    """Set up a test database with Tortoise ORM."""
    await Tortoise.init(config=tortoise_config, _create_db=True)
    yield
    await Tortoise.close_connections()
