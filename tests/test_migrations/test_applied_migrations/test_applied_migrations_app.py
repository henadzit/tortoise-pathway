"""
Tests for application with applied migrations.
"""

import pytest
from pathlib import Path

from tortoise import Tortoise
from tortoise_pathway.migration_manager import MigrationManager


@pytest.mark.parametrize("tortoise_config", ["test_applied_migrations"], indirect=True)
async def test_applied_migrations(setup_db_file, tortoise_config):
    """Test handling of already applied migrations."""
    # Initialize Tortoise ORM
    await Tortoise.init(config=tortoise_config)

    # Get the current directory (where the test file is located)
    test_dir = Path(__file__).parent
    migrations_dir = test_dir / "migrations"

    # Create migration manager and initialize it
    manager = MigrationManager(
        app_name="test_applied_migrations",
        migrations_dir=str(migrations_dir),
    )
    await manager.initialize()

    # Check that one migration exists but is not applied yet
    assert len(manager.migrations) == 1
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 1

    # Apply the migration
    applied = await manager.apply_migrations()
    assert len(applied) == 1

    # Verify migration was applied
    assert len(manager.get_applied_migrations()) == 1
    assert len(manager.get_pending_migrations()) == 0

    # Check the database to verify tables were created
    conn = Tortoise.get_connection("default")

    # For SQLite: check if tables exist
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('products', 'categories')"
    )

    # Should find both tables
    table_names = [record["name"] for record in result[1]]
    assert "products" in table_names
    assert "categories" in table_names

    # Initialize a new instance of the manager to simulate restarting the application
    new_manager = MigrationManager(
        app_name="test_applied_migrations",
        migrations_dir=str(migrations_dir),
    )
    await new_manager.initialize()

    # Verify the migration is recognized as already applied
    assert len(new_manager.migrations) == 1
    assert len(new_manager.get_applied_migrations()) == 1
    assert len(new_manager.get_pending_migrations()) == 0

    # Clean up
    await Tortoise.close_connections()
