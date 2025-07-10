"""
Tests for application with no migrations.
"""

import pytest
from pathlib import Path

from tortoise.indexes import Index

from tortoise_pathway.index_ext import UniqueIndex
from tortoise_pathway.migration_manager import MigrationManager
from tortoise_pathway.operations.add_index import AddIndex
from tortoise_pathway.operations.create_model import CreateModel


@pytest.mark.parametrize("tortoise_config", ["test_no_migrations"], indirect=True)
async def test_create_initial_migration(setup_test_db):
    """Test creating an initial migration when no migrations exist."""
    # Get the current directory (where the test file is located)
    test_dir = Path(__file__).parent
    migrations_dir = test_dir / "migrations"

    # Create migration manager and initialize it
    manager = MigrationManager(
        app_names=["test_no_migrations"],
        migrations_dir=str(migrations_dir),
    )
    await manager.initialize()

    # Verify no migrations exist initially
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 0

    # Create an initial migration
    created = []
    async for migration in manager.create_migrations("initial", auto=True):
        created.append(migration)
    assert len(created) == 1
    migration = created[0]
    assert migration.path().exists()

    # Re-discover migrations and verify the new migration is found
    # but not applied yet
    manager._discover_migrations()
    assert len(manager.get_applied_migrations()) == 0
    assert len(manager.get_pending_migrations()) == 1

    # Check migration file content
    with open(migration.path(), "r") as f:
        content = f.read()
        # Verify it includes table creation operations
        assert "CreateModel" in content
        assert 'model="test_no_migrations.User"' in content
        assert 'model="test_no_migrations.Note"' in content

    operations = migration.operations
    assert len(operations) == 4

    create_user_op = operations[0]
    assert isinstance(create_user_op, CreateModel)
    assert create_user_op.model == "test_no_migrations.User"

    assert isinstance(operations[1], AddIndex)
    assert operations[1].model == "test_no_migrations.User"
    assert isinstance(operations[1].index, Index)
    assert operations[1].index.name == "idx_users_name_6aafa3"
    assert operations[1].index.fields == ["name"]

    create_note_op = operations[2]
    assert isinstance(create_note_op, CreateModel)
    assert create_note_op.model == "test_no_migrations.Note"

    assert isinstance(operations[3], AddIndex)
    assert operations[3].model == "test_no_migrations.Note"
    assert isinstance(operations[3].index, UniqueIndex)
    assert operations[3].index.name == "uniq_notes_user_ti_70d5aa"
    assert operations[3].index.fields == ["user", "title"]

    applied = []
    async for migration in manager.apply_migrations():
        applied.append(migration)
    assert len(applied) == 1

    # Verify all migrations are now applied
    assert len(manager.get_applied_migrations()) == 1
    assert len(manager.get_pending_migrations()) == 0

    created = []
    async for migration in manager.create_migrations("no_changes", auto=True):
        created.append(migration)
    assert len(created) == 0
