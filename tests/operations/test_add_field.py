"""
Tests for AddField operation.
"""

from tortoise import fields
from tortoise_pathway.operations import AddField
from tortoise_pathway.state import State


class TestSqliteDialect:
    """Tests for AddField operation with SQLite dialect."""

    def test_add_regular_field(self):
        """Test SQL generation for adding a regular field."""
        state = State("test")
        state.schema["models"]["TestModel"] = {
            "table": "test_table",
            "app": "tests",
        }

        # Test adding a text field
        operation = AddField(
            model="tests.models.TestModel",
            field_object=fields.TextField(null=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, dialect="sqlite")

        assert sql == "ALTER TABLE test_table ADD COLUMN description TEXT"

        # Test adding a non-nullable field with default
        operation = AddField(
            model="tests.models.TestModel",
            field_object=fields.IntField(default=0),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, dialect="sqlite")

        assert sql == "ALTER TABLE test_table ADD COLUMN count INT NOT NULL DEFAULT 0"

    def test_add_foreign_key(self):
        """Test SQL generation for adding a foreign key field with SQLite."""
        state = State("test")

        # Set up models in the state
        state.schema["models"]["TestModel"] = {
            "table": "test_table",
            "app": "tests",
        }

        state.schema["models"]["User"] = {
            "table": "users",
            "app": "tests",
        }

        # Test adding a foreign key field
        operation = AddField(
            model="tests.models.TestModel",
            field_object=fields.ForeignKeyField("tests.User", related_name="test_models"),
            field_name="user",
        )

        sql = operation.forward_sql(state=state, dialect="sqlite")

        assert sql == "ALTER TABLE test_table ADD COLUMN user_id INT NOT NULL REFERENCES users(id)"

        # Test backward operation
        backward_sql = operation.backward_sql(state=state)
        assert "DROP COLUMN user_id" in backward_sql


class TestPostgresDialect:
    """Tests for AddField operation with PostgreSQL dialect."""

    def test_add_regular_field(self):
        """Test SQL generation for adding a regular field."""
        state = State("test")
        state.schema["models"]["TestModel"] = {
            "table": "test_table",
            "app": "tests",
        }

        # Test adding a text field
        operation = AddField(
            model="tests.models.TestModel",
            field_object=fields.TextField(null=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")

        assert sql == "ALTER TABLE test_table ADD COLUMN description TEXT"

    def test_add_foreign_key(self):
        """Test SQL generation for adding a foreign key field with PostgreSQL."""
        state = State("test")

        # Set up models in the state
        state.schema["models"]["TestModel"] = {
            "table": "test_table",
            "app": "tests",
        }

        state.schema["models"]["Category"] = {
            "table": "categories",
            "app": "tests",
        }

        # Test adding a foreign key field
        operation = AddField(
            model="tests.models.TestModel",
            field_object=fields.ForeignKeyField("tests.Category", related_name="test_models"),
            field_name="category",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")

        expected_sql = (
            "ALTER TABLE test_table ADD COLUMN category_id INT NOT NULL,\n"
            "ADD CONSTRAINT fk_test_table_category_id "
            "FOREIGN KEY (category_id) REFERENCES categories(id)"
        )

        assert sql == expected_sql
