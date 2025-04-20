"""
Tests for application with model changes after initial migration.
"""

import pytest
from pathlib import Path

from tortoise import Tortoise
from tortoise.exceptions import IntegrityError
from tortoise_pathway.migration_manager import MigrationManager
from tortoise_pathway.operations import (
    AddIndex,
    AlterField,
    CreateModel,
    AddField,
    DropField,
)


@pytest.mark.parametrize("tortoise_config", ["test_model_changes"], indirect=True)
async def test_model_changes(setup_test_db):
    """Test detecting and applying model changes after initial migration."""
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
    await conn.execute_query("SELECT * FROM blogs")
    await conn.execute_query("SELECT * FROM tags")
    with pytest.raises(Exception):
        await conn.execute_query("SELECT * FROM comments")

    # Detect changes and create a new migration
    migration = await manager.create_migration("model_changes", auto=True)
    assert migration.path().exists()

    # Verify operations in the migration
    # There should be operations for:
    # 1. Add 'summary' and 'updated_at' fields to 'blogs' table
    # 2. Add 'description' field to 'tags' table
    # 3. Create 'comments' table
    # 4. Drop 'content' field from 'blogs' table

    # Verify the exact operations and their order
    operations = migration.operations
    assert len(operations) == 8

    comments_table_op = operations[0]
    assert isinstance(comments_table_op, CreateModel)
    assert comments_table_op.get_table_name(manager.migration_state) == "comments"
    assert "id" in comments_table_op.fields
    assert "content" in comments_table_op.fields
    assert "author_name" in comments_table_op.fields
    assert "created_at" in comments_table_op.fields
    assert "blog" in comments_table_op.fields

    assert isinstance(operations[1], AddField)
    assert operations[1].get_table_name(manager.migration_state) == "blogs"
    assert operations[1].field_name == "summary"

    assert isinstance(operations[2], AddField)
    assert operations[2].get_table_name(manager.migration_state) == "blogs"
    assert operations[2].field_name == "updated_at"
    assert getattr(operations[2].field_object, "auto_now", False)

    assert isinstance(operations[3], DropField)
    assert operations[3].get_table_name(manager.migration_state) == "blogs"
    assert operations[3].field_name == "content"

    assert isinstance(operations[4], AlterField)
    assert operations[4].get_table_name(manager.migration_state) == "blogs"
    assert operations[4].field_name == "slug"
    assert operations[4].field_object is not None
    assert operations[4].field_object.unique

    assert isinstance(operations[5], AddIndex)
    assert operations[5].get_table_name(manager.migration_state) == "blogs"
    assert operations[5].field_name == "created_at"
    assert operations[5].index_name == "idx_created_at"
    assert not operations[5].unique

    assert isinstance(operations[6], AddField)
    assert operations[6].get_table_name(manager.migration_state) == "tags"
    assert operations[6].field_name == "description"

    assert isinstance(operations[7], AlterField)
    assert operations[7].get_table_name(manager.migration_state) == "tags"
    assert operations[7].field_name == "color"
    assert operations[7].field_object is not None
    assert operations[7].field_object.null
    assert operations[7].field_object.default == "red"

    # Verify field deletion operation

    # Re-discover migrations
    manager._discover_migrations()
    assert len(manager.migrations) == 2
    assert len(manager.get_applied_migrations()) == 1
    assert len(manager.get_pending_migrations()) == 1

    # Verify the migration file contains all expected changes
    with open(migration.path(), "r") as f:
        content = f.read()
        # Check for new fields
        assert "summary" in content
        assert "updated_at" in content
        assert "description" in content
        # Check for new model
        assert "comments" in content
        assert "author_name" in content
        # Check for dropped field
        assert "DropField" in content
        assert "content" in content

    # Apply the new migration
    applied = await manager.apply_migrations()
    assert len(applied) == 1

    # Verify all migrations are now applied
    assert len(manager.get_applied_migrations()) == 2
    assert len(manager.get_pending_migrations()) == 0

    # Check the database to verify changes were applied
    # 1. Verify new table was created
    await conn.execute_query("SELECT * FROM comments")

    await conn.execute_query(
        "INSERT INTO blogs (slug, title, summary) VALUES ('test-slug', 'Test Title', 'Test Summary')"
    )
    with pytest.raises(IntegrityError):
        # This should raise an IntegrityError because the slug is now unique
        await conn.execute_query(
            "INSERT INTO blogs (slug, title) VALUES ('test-slug', 'Another Title')"
        )

    res = await conn.execute_query("SELECT created_at, updated_at FROM blogs")
    assert res[1][0]["created_at"] is not None
    assert res[1][0]["updated_at"] is not None

    # Verify nullability change
    await conn.execute_query("INSERT INTO tags (name, color) VALUES ('test-tag', null)")
    res = await conn.execute_query("SELECT color FROM tags")
    assert res[1][0]["color"] is None

    await conn.execute_query("DELETE FROM tags")

    # Verify default value change
    await conn.execute_query("INSERT INTO tags (name) VALUES ('test-tag')")
    res = await conn.execute_query("SELECT color FROM tags")
    assert res[1][0]["color"] == "red"
