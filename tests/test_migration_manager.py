import pytest
from unittest.mock import Mock

from tortoise_pathway.migration import Migration
from tortoise_pathway.migration_manager import sort_migrations


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
        migration1.name.return_value = "migration1"
        migration1.dependencies = []

        migration2 = Mock(spec=Migration)
        migration2.name.return_value = "migration2"
        migration2.dependencies = ["migration1"]

        migration3 = Mock(spec=Migration)
        migration3.name.return_value = "migration3"
        migration3.dependencies = ["migration2"]

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
        migration1.name.return_value = "migration1"
        migration1.dependencies = []

        migration2 = Mock(spec=Migration)
        migration2.name.return_value = "migration2"
        migration2.dependencies = ["migration1"]

        migration3 = Mock(spec=Migration)
        migration3.name.return_value = "migration3"
        migration3.dependencies = ["migration1"]

        migration4 = Mock(spec=Migration)
        migration4.name.return_value = "migration4"
        migration4.dependencies = ["migration2", "migration3"]

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
