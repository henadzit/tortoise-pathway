"""
Tests for application with no migrations.
"""

import pytest
from pathlib import Path

from tortoise import Tortoise
from tortoise_pathway.migration import MigrationManager


@pytest.mark.parametrize("tortoise_config", ["test_no_migrations"], indirect=True)
async def test_create_initial_migration(setup_db_file, tortoise_config):
    """Test creating an initial migration when no migrations exist."""
    # Initialize Tortoise ORM
    await Tortoise.init(config=tortoise_config)

    # Get the current directory (where the test file is located)
    test_dir = Path(__file__).parent
    migrations_dir = test_dir / "migrations"

    # Create migration manager and initialize it
    manager = MigrationManager(
        app_name="test_no_migrations",
        migrations_dir=str(migrations_dir),
    )
    await manager.initialize()

    # Verify no migrations exist initially
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 0

    # Create an initial migration
    migration_file = await manager.create_migration("initial", auto=True)
    assert migration_file.exists()

    # Re-discover migrations and verify the new migration is found
    # but not applied yet
    manager._discover_migrations()
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 1

    # Check migration file content
    with open(migration_file, "r") as f:
        content = f.read()
        # Verify it includes table creation operations
        assert "CreateTable" in content
        assert 'table_name="users"' in content
        assert 'table_name="notes"' in content

    # Clean up
    await Tortoise.close_connections()
