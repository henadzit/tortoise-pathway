"""
Tests for RenameField operation.
"""

import pytest
from tortoise import Tortoise, fields

from tortoise_pathway.operations import CreateModel, RenameField
from tortoise_pathway.schema.sqlite import SqliteSchemaManager
from tortoise_pathway.state import State


async def test_rename_field(setup_test_db):
    """Test RenameField operation with field rename."""
    state = State("tests")

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_rename_field",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Verify original field exists
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT name FROM test_rename_field")

    # Rename the field
    operation = RenameField(
        model="tests.TestModel",
        field_name="name",
        new_field_name="full_name",
    )
    await operation.apply(state=state)

    # Verify field was renamed
    await conn.execute_query("SELECT full_name FROM test_rename_field")
    with pytest.raises(Exception):
        await conn.execute_query("SELECT name FROM test_rename_field")


def test_forward_sql():
    """Test SQL generation for SQLite dialect."""
    state = State("tests")
    state.apply_operation(
        CreateModel(
            model="tests.TestModel",
            table="test_rename_field_sql",
            fields={
                "id": fields.IntField(primary_key=True),
                "name": fields.CharField(max_length=100),
            },
        )
    )

    operation = RenameField(
        model="tests.TestModel",
        field_name="name",
        new_field_name="full_name",
    )

    sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())
    assert sql == "ALTER TABLE test_rename_field_sql RENAME COLUMN name TO full_name"


def test_backward_sql():
    """Test SQL generation for SQLite dialect."""
    state = State("tests")
    state.apply_operation(
        CreateModel(
            model="tests.TestModel",
            table="test_rename_field_sql",
            fields={
                "id": fields.IntField(primary_key=True),
                "name": fields.CharField(max_length=100),
            },
        )
    )
    state.snapshot("test_backward_sql")

    operation = RenameField(
        model="tests.TestModel",
        field_name="name",
        new_field_name="full_name",
    )
    state.apply_operation(operation)
    state.snapshot("test_backward_sql_2")

    sql = operation.backward_sql(state=state, schema_manager=SqliteSchemaManager())
    assert sql == "ALTER TABLE test_rename_field_sql RENAME COLUMN full_name TO name"


def test_to_migration():
    """Test migration code generation."""
    operation = RenameField(
        model="tests.TestModel",
        field_name="name",
        new_field_name="full_name",
        new_column_name="user_full_name",
    )

    migration_code = operation.to_migration()
    expected = """RenameField(
    model="tests.TestModel",
    field_name="name",
    new_field_name="full_name",
    new_column_name="user_full_name",
)"""
    assert migration_code == expected
