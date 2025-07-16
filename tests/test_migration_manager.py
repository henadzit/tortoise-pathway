import pytest
from unittest.mock import Mock, patch
from typing import List, Dict
from tortoise.fields import CharField, IntField, Field

from tortoise_pathway.migration import Migration
from tortoise_pathway.migration_manager import (
    sort_migrations,
    gen_name_from_changes,
    MigrationManager,
)
from tortoise_pathway.operations import Operation, CreateModel, AddField, AlterField
from tortoise_pathway.state import State


class TestSortMigrations:
    def test_empty_migrations_list(self):
        """Test sorting an empty list of migrations."""
        assert sort_migrations([]) == []

    def test_single_migration_no_dependencies(self):
        """Test sorting a single migration with no dependencies."""
        migration = Mock(spec=Migration)
        migration.name.return_value = "migration1"
        migration.dependencies = []

        result = sort_migrations([migration])

        assert len(result) == 1
        assert result[0].name() == "migration1"

    def test_linear_dependencies(self):
        """Test sorting migrations with linear dependencies."""
        migration1 = Mock(spec=Migration)
        migration1.app_name = "app"
        migration1.name.return_value = "migration1"
        migration1.dependencies = []

        migration2 = Mock(spec=Migration)
        migration2.app_name = "app"
        migration2.name.return_value = "migration2"
        migration2.dependencies = [("app", "migration1")]

        migration3 = Mock(spec=Migration)
        migration3.app_name = "app"
        migration3.name.return_value = "migration3"
        migration3.dependencies = [("app", "migration2")]

        # Test with different input orders
        result1 = sort_migrations([migration1, migration2, migration3])
        result2 = sort_migrations([migration3, migration2, migration1])
        result3 = sort_migrations([migration2, migration1, migration3])

        expected_names = ["migration1", "migration2", "migration3"]

        assert [m.name() for m in result1] == expected_names
        assert [m.name() for m in result2] == expected_names
        assert [m.name() for m in result3] == expected_names

    def test_multiple_dependencies(self):
        """Test sorting migrations with multiple dependencies."""
        migration1 = Mock(spec=Migration)
        migration1.app_name = "app"
        migration1.name.return_value = "migration1"
        migration1.dependencies = []

        migration2 = Mock(spec=Migration)
        migration2.app_name = "app"
        migration2.name.return_value = "migration2"
        migration2.dependencies = [("app", "migration1")]

        migration3 = Mock(spec=Migration)
        migration3.app_name = "app"
        migration3.name.return_value = "migration3"
        migration3.dependencies = [("app", "migration1")]

        migration4 = Mock(spec=Migration)
        migration4.app_name = "app"
        migration4.name.return_value = "migration4"
        migration4.dependencies = [("app", "migration2"), ("app", "migration3")]

        result = sort_migrations([migration4, migration3, migration2, migration1])

        # Check that dependencies come before dependents
        result_names = [m.name() for m in result]
        assert result_names.index("migration1") < result_names.index("migration2")
        assert result_names.index("migration1") < result_names.index("migration3")
        assert result_names.index("migration2") < result_names.index("migration4")
        assert result_names.index("migration3") < result_names.index("migration4")

    def test_multiple_root_migrations_error(self):
        """Test that an error is raised when multiple root migrations are found."""
        migration1 = Mock(spec=Migration)
        migration1.name.return_value = "migration1"
        migration1.dependencies = []

        migration2 = Mock(spec=Migration)
        migration2.name.return_value = "migration2"
        migration2.dependencies = []

        with pytest.raises(ValueError, match="Multiple root migrations found"):
            sort_migrations([migration1, migration2])

    def test_circular_dependency_error(self):
        """Test that an error is raised when circular dependencies are detected."""
        migration0 = Mock(spec=Migration, name="migration0")
        migration0.name.return_value = "migration0"
        migration0.dependencies = []

        migration1 = Mock(spec=Migration, name="migration1")
        migration1.name.return_value = "migration1"
        migration1.dependencies = ["migration2", "migration0"]

        migration2 = Mock(spec=Migration, name="migration2")
        migration2.name.return_value = "migration2"
        migration2.dependencies = ["migration3"]

        migration3 = Mock(spec=Migration, name="migration3")
        migration3.name.return_value = "migration3"
        migration3.dependencies = ["migration1"]

        with pytest.raises(ValueError, match="Circular dependency detected"):
            sort_migrations([migration0, migration1, migration2, migration3])

    def test_no_root_migration_error(self):
        """Test that an error is raised when no root migration is found."""
        migration1 = Mock(spec=Migration)
        migration1.name.return_value = "migration1"
        migration1.dependencies = ["migration2"]

        migration2 = Mock(spec=Migration)
        migration2.name.return_value = "migration2"
        migration2.dependencies = ["migration1"]

        with pytest.raises(ValueError, match="No root migration found"):
            sort_migrations([migration1, migration2])


class TestGenNameFromChanges:
    def test_empty_changes_list(self):
        """Test with an empty list of changes."""
        assert gen_name_from_changes([]) == "auto"

    def test_single_model_no_fields(self):
        """Test with changes affecting a single model but no specific fields."""
        fields: Dict[str, Field] = {"id": IntField(primary_key=True)}
        changes: List[Operation] = [
            CreateModel("app.User", "users", fields),
        ]
        assert gen_name_from_changes(changes) == "user"

    def test_single_model_single_field(self):
        """Test with changes affecting a single model and single field."""
        changes: List[Operation] = [
            AddField("app.User", CharField(max_length=255), "email"),
        ]
        assert gen_name_from_changes(changes) == "user_email"

    def test_single_model_multiple_fields(self):
        """Test with changes affecting a single model but multiple fields."""
        changes: List[Operation] = [
            AddField("app.User", CharField(max_length=255), "email"),
            AddField("app.User", CharField(max_length=100), "username"),
        ]
        assert gen_name_from_changes(changes) == "user"

    def test_multiple_models(self):
        """Test with changes affecting multiple models."""
        changes: List[Operation] = [
            AddField("app.User", CharField(max_length=255), "email"),
            AddField("app.Profile", CharField(max_length=500), "bio"),
        ]
        assert gen_name_from_changes(changes) == "auto"

    def test_mixed_operation_types(self):
        """Test with a mix of different operation types."""
        changes: List[Operation] = [
            CreateModel("app.User", "users", {"id": IntField(primary_key=True)}),
            AddField("app.User", CharField(max_length=255), "email"),
        ]
        assert gen_name_from_changes(changes) == "user"

    def test_operation_without_field_name(self):
        """Test with operation that doesn't have field_name attribute."""
        # AlterField alters field but retains the same field_name
        changes: List[Operation] = [
            AlterField("app.User", CharField(max_length=50), "username"),
        ]
        assert gen_name_from_changes(changes) == "user_username"


class TestGetPendingMigrationsSql:
    """Test the get_pending_migrations_sql method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = MigrationManager(["test_app", "other_app"])
        self.manager.applied_state = State()
        self.manager.migrations = []
        self.manager.applied_migrations = set()

    @patch("tortoise_pathway.migration_manager.connections")
    def test_empty_pending_migrations(self, mock_connections):
        """Test when there are no pending migrations."""
        # Mock connection and schema manager
        mock_connection = Mock()
        mock_connection.capabilities.dialect = "sqlite"
        mock_connections.get.return_value = mock_connection

        result = self.manager.get_pending_migrations_sql()

        assert result == ""

    @patch("tortoise_pathway.migration_manager.connections")
    def test_multiple_pending_migrations(self, mock_connections):
        """Test with multiple pending migrations."""
        # Mock connection and schema manager
        mock_connection = Mock()
        mock_connection.capabilities.dialect = "postgres"
        mock_connections.get.return_value = mock_connection

        class Migration1(Migration):
            app_name = "test_app"
            operations = [
                CreateModel("test_app.User", "users", {"id": IntField(primary_key=True)}),
            ]

        class Migration2(Migration):
            app_name = "test_app"
            operations = [
                AddField("test_app.User", CharField(max_length=255), "email"),
            ]

        # Set up the manager state
        self.manager.migrations = [Migration1, Migration2]
        self.manager.applied_migrations = set()  # No applied migrations

        result = self.manager.get_pending_migrations_sql()

        expected_sql = """-- Migration: test_app -> test_migration_manager
CREATE TABLE "users" (
    id SERIAL PRIMARY KEY
);
-- Migration: test_app -> test_migration_manager
ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"""

        assert result == expected_sql
