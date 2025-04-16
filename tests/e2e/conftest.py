import os
from pathlib import Path
from typing import Any, Dict

import pytest


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


@pytest.fixture(autouse=True)
async def clean_migrations():
    """Clean up migrations directory after tests."""

    test_migrations_dir = Path(os.getcwd()) / "tests" / "e2e"

    def _cleanup():
        for item in test_migrations_dir.glob("*/migrations/*/*.py"):
            if item.is_file() and item.name != "__init__.py" and "donotdelete" not in item.name:
                print(f"Removing migration file: {item}")
                item.unlink()

    _cleanup()

    yield

    _cleanup()
