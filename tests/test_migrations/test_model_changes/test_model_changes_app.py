"""
Tests for application with model changes after initial migration.
"""

import pytest
import os
from pathlib import Path

from tortoise import Tortoise
from tortoise_pathway.migration_manager import MigrationManager
from tortoise_pathway.operations import (
    AddIndex,
    AlterField,
    CreateModel,
    AddField,
    DropField,
)


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
    assert len(operations) == 7

    comments_table_op = operations[0]
    assert isinstance(comments_table_op, CreateModel)
    assert comments_table_op.get_table_name(manager.state) == "comments"
    assert "id" in comments_table_op.fields
    assert "content" in comments_table_op.fields
    assert "author_name" in comments_table_op.fields
    assert "created_at" in comments_table_op.fields
    assert "blog_id" in comments_table_op.fields

    assert isinstance(operations[1], AddField)
    assert operations[1].get_table_name(manager.state) == "blogs"
    assert operations[1].field_name == "summary"

    assert isinstance(operations[2], AddField)
    assert operations[2].get_table_name(manager.state) == "blogs"
    assert operations[2].field_name == "updated_at"

    assert isinstance(operations[3], DropField)
    assert operations[3].get_table_name(manager.state) == "blogs"
    assert operations[3].field_name == "content"

    assert isinstance(operations[4], AlterField)
    assert operations[4].get_table_name(manager.state) == "blogs"
    assert operations[4].field_name == "slug"
    assert operations[4].field_object is not None
    assert operations[4].field_object.unique

    assert isinstance(operations[5], AddIndex)
    assert operations[5].get_table_name(manager.state) == "blogs"
    assert operations[5].field_name == "created_at"
    assert operations[5].index_name == "idx_created_at"
    assert not operations[5].unique

    assert isinstance(operations[6], AddField)
    assert operations[6].get_table_name(manager.state) == "tags"
    assert operations[6].field_name == "description"

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
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='comments'"
    )
    assert len(result[1]) == 1

    # 2. Verify new columns were added to existing tables
    blog_columns = await conn.execute_query("PRAGMA table_info(blogs)")
    blog_column_names = [column["name"] for column in blog_columns[1]]
    assert "summary" in blog_column_names
    assert "updated_at" in blog_column_names
    # Verify deleted column is no longer present
    assert "content" not in blog_column_names

    tag_columns = await conn.execute_query("PRAGMA table_info(tags)")
    tag_column_names = [column["name"] for column in tag_columns[1]]
    assert "description" in tag_column_names

    # Verify the unique index on the slug field
    indexes = await conn.execute_query("PRAGMA index_list('blogs')")
    index_names = [idx["name"] for idx in indexes[1]]

    # Find any index that might be on the slug column
    slug_index = None
    for index_name in index_names:
        index_info = await conn.execute_query(f"PRAGMA index_info('{index_name}')")
        for column_info in index_info[1]:
            if column_info["name"] == "slug":
                slug_index = index_name
                break
        if slug_index:
            break

    assert slug_index is not None, "No index found for the slug column"

    # Check if the index is unique
    for idx in indexes[1]:
        if idx["name"] == slug_index:
            assert idx["unique"] == 1, "The index on slug is not unique"
            break

    # Clean up
    await Tortoise.close_connections()
