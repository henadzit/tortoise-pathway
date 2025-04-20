"""
Tests for AlterField operation.
"""

from tortoise import fields
from tortoise_pathway.operations import AlterField
from tortoise_pathway.state import State


class TestSqliteDialect:
    """Tests for AlterField operation with SQLite dialect."""

    def test_alter_field_type(self):
        """Test SQL generation for altering a field type."""
        # Create state with proper model and field
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"name": fields.TextField(null=True)},
                    }
                }
            },
        )

        # Change the field type to CharField
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.CharField(max_length=50, null=True),
            field_name="name",
        )

        sql = operation.forward_sql(state=state, dialect="sqlite")
        assert (
            sql
            == """BEGIN TRANSACTION;
CREATE TABLE "__new__test_table" (
    name VARCHAR(50)
);;
INSERT INTO __new__test_table (name)
SELECT name FROM test_table;
DROP TABLE test_table;
ALTER TABLE __new__test_table RENAME TO test_table;
COMMIT;"""
        )

    def test_alter_field_default(self):
        """Test SQL generation for altering a field's default value."""
        # Create state with proper model and field
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"count": fields.IntField(default=0)},
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.IntField(default=10),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, dialect="sqlite")
        assert (
            sql
            == """BEGIN TRANSACTION;
CREATE TABLE "__new__test_table" (
    count INT NOT NULL DEFAULT 10
);;
INSERT INTO __new__test_table (count)
SELECT count FROM test_table;
DROP TABLE test_table;
ALTER TABLE __new__test_table RENAME TO test_table;
COMMIT;"""
        )


class TestPostgresDialect:
    """Tests for AlterField operation with PostgreSQL dialect."""

    def test_alter_field_type(self):
        """Test SQL generation for altering a field type in PostgreSQL."""
        # Create state with proper model and field
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"count": fields.IntField()},
                    }
                }
            },
        )

        # Change IntField to BigIntField
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.BigIntField(),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")
        assert sql == "ALTER TABLE test_table ALTER COLUMN count TYPE BIGINT;"

    def test_alter_field_default(self):
        """Test SQL generation for altering a field's default value in PostgreSQL."""
        # Create state with proper model and field with default
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"count": fields.IntField(default=0)},
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.IntField(default=10),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")
        assert sql == "ALTER TABLE test_table ALTER COLUMN count SET DEFAULT 10;"

    def test_alter_field_unique(self):
        """Test SQL generation for making a field unique in PostgreSQL."""
        # Create state with non-unique field
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"email": fields.CharField(max_length=255, unique=False)},
                    }
                }
            },
        )

        # Make the field unique
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.CharField(max_length=255, unique=True),
            field_name="email",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")
        assert sql == "ALTER TABLE test_table ADD CONSTRAINT email_unique UNIQUE (email);"

    def test_alter_field_default_unique(self):
        """Test SQL generation for altering a field's default value in PostgreSQL."""
        # Create state with proper model and field with default
        state = State(
            "tests",
            {
                "models": {
                    "TestModel": {
                        "table": "test_table",
                        "fields": {"count": fields.IntField(default=0)},
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.IntField(default=10, unique=True),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, dialect="postgres")
        assert (
            sql
            == """ALTER TABLE test_table ALTER COLUMN count SET DEFAULT 10;
ALTER TABLE test_table ADD CONSTRAINT count_unique UNIQUE (count);"""
        )

    def test_to_migration(self):
        """Test generating migration code for AlterField."""
        operation = AlterField(
            model="tests.TestModel",
            field_object=fields.CharField(max_length=100, null=True),
            field_name="name",
        )

        migration_code = operation.to_migration()
        assert (
            migration_code
            == """AlterField(
    model="tests.TestModel",
    field_object=CharField(null=True, max_length=100),
    field_name="name",
)"""
        )
