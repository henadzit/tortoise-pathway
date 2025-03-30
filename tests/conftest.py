"""
Pytest configuration and fixtures for Tortoise Pathway tests.
"""

import os
import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, Generator, AsyncGenerator

from tortoise import Tortoise
from tortoise_pathway.migration_manager import MigrationManager


@pytest.fixture(autouse=True)
async def clean_apps():
    """Clean up Tortoise apps after tests."""
    Tortoise.apps = {}


@pytest.fixture(autouse=True)
async def clean_migrations():
    """Clean up migrations directory after tests."""

    test_migrations_dir = Path(os.getcwd()) / "tests" / "test_migrations"

    def _cleanup():
        for item in test_migrations_dir.glob("*/migrations/*.py"):
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
async def tortoise_config(setup_db_file: Path, request) -> Dict[str, Any]:
    """Create a Tortoise ORM configuration for tests."""
    app_name = request.param if hasattr(request, "param") else "models"

    # The actual test path is determined dynamically from the test file's location
    test_path = Path(request.node.fspath).parent

    # Construct the models module path correctly
    # First get the relative path from the project root to the test directory
    rel_path = test_path.relative_to(Path.cwd())
    # Convert the path to a module path (replacing / with .)
    models_module = str(rel_path).replace("/", ".") + ".models"

    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": str(setup_db_file)},
            },
        },
        "apps": {
            app_name: {
                "models": [models_module],
                "default_connection": "default",
            },
        },
        "use_tz": False,
    }


@pytest.fixture
async def migration_manager(
    tortoise_config: Dict[str, Any], setup_db_file: Path, request
) -> MigrationManager:
    """Create a migration manager for tests."""
    # Get the test app name from the test path
    test_path = Path(request.node.fspath).parent
    app_name = test_path.name

    # Set up migrations directory
    migrations_dir = test_path / "migrations"
    os.makedirs(migrations_dir, exist_ok=True)

    # Create the migration manager
    manager = MigrationManager(
        app_name=app_name,
        migrations_dir=str(migrations_dir),
    )

    # Initialize the migration manager
    await manager.initialize()

    return manager
