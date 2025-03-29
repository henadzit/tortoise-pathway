"""
Tests for application with model changes after initial migration.
"""

import os
import pytest
from pathlib import Path

import tortoise_pathway
from tortoise import Tortoise
from tortoise_pathway.migration import MigrationManager


@pytest.mark.parametrize("tortoise_config", ["test_model_changes"], indirect=True)
async def test_model_changes(setup_db_file, tortoise_config):
    """Test detecting and applying model changes after initial migration."""
    # Initialize Tortoise ORM
    await Tortoise.init(config=tortoise_config)

    # Get the current directory (where the test file is located)
    test_dir = Path(__file__).parent
    migrations_dir = test_dir / "migrations"

    # Create migration manager and initialize it
    manager = MigrationManager(
        app_name="test_model_changes",
        migrations_dir=str(migrations_dir),
    )
    await manager.initialize()

    # Check that the initial migration exists but is not applied yet
    assert len(manager.migrations) == 1
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 1

    # Apply the initial migration
    applied = await manager.apply_migrations()
    assert len(applied) == 1

    # Check the database to verify initial tables were created
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('blogs', 'tags', 'comments')"
    )

    # Should find blogs and tags but not comments
    table_names = [record["name"] for record in result[1]]
    assert "blogs" in table_names
    assert "tags" in table_names
    assert "comments" not in table_names

    # Detect changes and create a new migration
    migration_file = await manager.create_migration("model_changes", auto=True)
    assert migration_file.exists()

    # Re-discover migrations
    manager._discover_migrations()
    assert len(manager.migrations) == 2
    assert len(manager.get_applied_migrations()) == 1
    assert len(manager.get_pending_migrations()) == 1

    # Verify the migration file contains all expected changes
    with open(migration_file, "r") as f:
        content = f.read()
        # Check for new fields
        assert "summary" in content
        assert "updated_at" in content
        assert "description" in content
        # Check for new model
        assert "comments" in content
        assert "author_name" in content

    # Apply the new migration
    applied = await manager.apply_migrations()
    assert len(applied) == 1

    # Verify all migrations are now applied
    assert len(manager.get_applied_migrations()) == 2
    assert len(manager.get_pending_migrations()) == 0

    # Check the database to verify changes were applied
    # 1. Verify new table was created
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='comments'"
    )
    assert len(result[1]) == 1

    # 2. Verify new columns were added to existing tables
    blog_columns = await conn.execute_query("PRAGMA table_info(blogs)")
    blog_column_names = [column["name"] for column in blog_columns[1]]
    assert "summary" in blog_column_names
    assert "updated_at" in blog_column_names

    tag_columns = await conn.execute_query("PRAGMA table_info(tags)")
    tag_column_names = [column["name"] for column in tag_columns[1]]
    assert "description" in tag_column_names

    # Clean up
    await Tortoise.close_connections()
