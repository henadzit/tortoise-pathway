"""
Tests for AlterField operation.
"""

from enum import Enum
from tortoise import fields
from tortoise.fields.data import CharEnumFieldInstance
from tortoise_pathway.operations import AlterField
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.schema.sqlite import SqliteSchemaManager
from tortoise_pathway.state import State


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class TestSqliteDialect:
    """Tests for AlterField operation with SQLite dialect."""

    def test_alter_field_type(self):
        """Test SQL generation for altering a field type."""
        # Create state with proper model and field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"name": fields.TextField(null=True)},
                        }
                    }
                }
            },
        )

        # Change the field type to CharField
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=50, null=True),
            field_name="name",
        )

        sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())
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
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"count": fields.IntField(default=0)},
                        }
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.IntField(default=10),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())
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

    def test_change_type(self):
        """Test SQL generation for altering a field type in PostgreSQL."""
        # Create state with proper model and field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"count": fields.IntField()},
                        }
                    }
                }
            },
        )

        # Change IntField to BigIntField
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.BigIntField(),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "ALTER TABLE test_table ALTER COLUMN count TYPE BIGINT;"

    def test_change_default(self):
        """Test SQL generation for altering a field's default value in PostgreSQL."""
        # Create state with proper model and field with default
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"count": fields.IntField(default=0)},
                        }
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.IntField(default=10),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "ALTER TABLE test_table ALTER COLUMN count SET DEFAULT 10;"

    def test_add_unique(self):
        """Test SQL generation for making a field unique in PostgreSQL."""
        # Create state with non-unique field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"email": fields.CharField(max_length=255, unique=False)},
                        }
                    }
                }
            },
        )

        # Make the field unique
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=255, unique=True),
            field_name="email",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "ALTER TABLE test_table ADD CONSTRAINT email_key UNIQUE (email);"

    def test_remove_unique(self):
        """Test SQL generation for removing a unique constraint in PostgreSQL."""
        # Create state with a unique field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"email": fields.CharField(max_length=255, unique=True)},
                        }
                    }
                }
            },
        )

        # Remove the unique constraint
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=255),
            field_name="email",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "ALTER TABLE test_table DROP CONSTRAINT email_key;"

    def test_default_unique_changed(self):
        """Test SQL generation for altering a field's default value in PostgreSQL."""
        # Create state with proper model and field with default
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"count": fields.IntField(default=0)},
                        }
                    }
                }
            },
        )

        # Change the default value
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.IntField(default=10, unique=True),
            field_name="count",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert (
            sql
            == """ALTER TABLE test_table ALTER COLUMN count SET DEFAULT 10;
ALTER TABLE test_table ADD CONSTRAINT count_key UNIQUE (count);"""
        )

    def test_add_index(self):
        """Test SQL generation for making a field indexed in PostgreSQL."""
        # Create state with non-unique field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"email": fields.CharField(max_length=255, db_index=False)},
                        }
                    }
                }
            },
        )

        # Make the field unique
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=255, db_index=True),
            field_name="email",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "CREATE INDEX idx_test_table_email ON test_table (email)"

    def test_remove_index(self):
        """Test SQL generation for removing an index in PostgreSQL."""
        # Create state with an indexed field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"email": fields.CharField(max_length=255, db_index=True)},
                        }
                    }
                }
            },
        )

        # Remove the index
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=255),
            field_name="email",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert sql == "DROP INDEX idx_test_table_email"

    def test_add_index_long_name(self):
        """Test SQL generation for making a field indexed in PostgreSQL."""
        # Create state with non-unique field
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table_for_long_index_name",
                            "fields": {
                                "email_address_for_long_index_name": fields.CharField(
                                    max_length=255, db_index=False
                                )
                            },
                        }
                    }
                }
            },
        )

        # Make the field unique
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=255, db_index=True),
            field_name="email_address_for_long_index_name",
        )

        sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
        assert (
            sql
            == "CREATE INDEX idx_test_table__email_a_596fb3 ON test_table_for_long_index_name (email_address_for_long_index_name)"
        )

    def test_to_migration(self):
        """Test generating migration code for AlterField."""
        operation = AlterField(
            model="test.TestModel",
            field_object=fields.CharField(max_length=100, null=True),
            field_name="name",
        )

        migration_code = operation.to_migration()
        assert (
            migration_code
            == """AlterField(
    model="test.TestModel",
    field_object=CharField(null=True, max_length=100),
    field_name="name",
)"""
        )

    def test_char_to_enum(self):
        """Test converting CharField to CharEnumField in PostgreSQL.

        Since Tortoise does not create a type in the database schema, this should be no op.
        """
        # Create state with a CharField
        state = State(
            schema={
                "test": {
                    "models": {
                        "TestModel": {
                            "table": "test_table",
                            "fields": {"role": fields.CharField(max_length=20)},
                        }
                    }
                }
            },
        )

        # Change to CharEnumField
        operation = AlterField(
            model="test.TestModel",
            field_object=CharEnumFieldInstance(enum_type=UserRole, max_length=20),
            field_name="role",
        )

        assert operation.forward_sql(state=state, schema_manager=PostgresSchemaManager()) == ""
