"""
Tests for AddField operation.
"""

from tortoise import fields
from tortoise_pathway.operations import AddField
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.schema.sqlite import SqliteSchemaManager
from tortoise_pathway.state import State


class TestSqliteDialect:
    """Tests for AddField operation with SQLite dialect."""

    def test_add_regular_field(self):
        """Test SQL generation for adding a regular field."""
        state = State(schema={"test": {"models": {"TestModel": {"table": "test_table"}}}})

        # Test adding a text field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.TextField(null=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())

        assert sql == "ALTER TABLE test_table ADD COLUMN description TEXT"

        # Test adding a non-nullable field with default
        operation = AddField(
            model="test.TestModel",
            field_object=fields.IntField(default=0),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())

        assert sql == "ALTER TABLE test_table ADD COLUMN count INT NOT NULL DEFAULT 0"

    def test_add_field_with_index(self):
        """Test SQL generation for adding a regular field."""
        state = State(schema={"test": {"models": {"TestModel": {"table": "test_table"}}}})

        # Test adding a text field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=100, null=True, db_index=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())

        assert (
            sql
            == "ALTER TABLE test_table ADD COLUMN description VARCHAR(100);\nCREATE INDEX idx_test_table_description ON test_table (description)"
        )

    def test_add_foreign_key(self):
        """Test SQL generation for adding a foreign key field with SQLite."""
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {"table": "test_table"},
                        "User": {"table": "users"},
                    }
                }
            },
        )

        # Test adding a foreign key field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.ForeignKeyField("test.User", related_name="test_models"),
            field_name="user",
        )

        sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())

        assert sql == "ALTER TABLE test_table ADD COLUMN user_id INT NOT NULL REFERENCES users(id)"

        # Test backward operation
        backward_sql = operation.backward_sql(state=state, schema_manager=SqliteSchemaManager())
        assert "DROP COLUMN user_id" in backward_sql


class TestPostgresDialect:
    """Tests for AddField operation with PostgreSQL dialect."""

    def test_add_regular_field(self):
        """Test SQL generation for adding a regular field."""
        state = State(schema={"test": {"models": {"TestModel": {"table": "test_table"}}}})

        # Test adding a text field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.TextField(null=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())

        assert sql == "ALTER TABLE test_table ADD COLUMN description TEXT"

    def test_add_field_with_index(self):
        """Test SQL generation for adding a regular field."""
        state = State(schema={"test": {"models": {"TestModel": {"table": "test_table"}}}})

        # Test adding an indexed char field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=100, null=True, db_index=True),
            field_name="description",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())

        assert (
            sql
            == "ALTER TABLE test_table ADD COLUMN description VARCHAR(100);\nCREATE INDEX idx_test_table_description ON test_table (description)"
        )

    def test_add_foreign_key(self):
        """Test SQL generation for adding a foreign key field with PostgreSQL."""
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {"table": "test_table"},
                        "Category": {"table": "categories"},
                    }
                }
            },
        )

        # Test adding a foreign key field
        operation = AddField(
            model="test.TestModel",
            field_object=fields.ForeignKeyField("test.Category", related_name="test_models"),
            field_name="category",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())

        expected_sql = (
            "ALTER TABLE test_table ADD COLUMN category_id INT NOT NULL,\n"
            "ADD CONSTRAINT fk_test_table_category_id "
            "FOREIGN KEY (category_id) REFERENCES categories(id)"
        )

        assert sql == expected_sql
