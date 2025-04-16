import os
import pytest
from pathlib import Path
from typing import AsyncGenerator

from tortoise import Tortoise


@pytest.fixture(autouse=True)
async def clean_apps():
    """Clean up Tortoise apps after tests."""
    Tortoise.apps = {}


@pytest.fixture(autouse=True)
async def clean_migrations():
    """Clean up migrations directory after tests."""

    test_migrations_dir = Path(os.getcwd()) / "tests" / "test_migrations"

    def _cleanup():
        for item in test_migrations_dir.glob("*/migrations/*/*.py"):
            if item.is_file() and item.name != "__init__.py" and "donotdelete" not in item.name:
                print(f"Removing migration file: {item}")
                item.unlink()

    _cleanup()

    yield

    _cleanup()


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
async def setup_test_db(setup_db_file):
    """Set up a test database with Tortoise ORM."""
    config = {
        "connections": {
            "default": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": str(setup_db_file)},
            },
        },
        "apps": {
            "test": {
                "models": ["tests.models"],
                "default_connection": "default",
            }
        },
    }

    await Tortoise.init(config=config)
    yield
    await Tortoise.close_connections()
