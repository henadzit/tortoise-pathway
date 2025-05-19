"""
Tests for RenameModel operation.
"""

import pytest
from tortoise import Tortoise, fields

from tortoise_pathway.operations import CreateModel, RenameModel
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.schema.sqlite import SqliteSchemaManager
from tortoise_pathway.state import State


async def test_rename_table(setup_test_db):
    """Test RenameModel operation with table rename."""
    state = State("tests")

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_rename",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Verify original table exists
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT * FROM test_rename")

    # Rename the table
    operation = RenameModel(
        model="tests.TestModel",
        new_table_name="renamed_test_table",
    )
    await operation.apply(state=state)

    # Verify table was renamed
    await conn.execute_query("SELECT * FROM renamed_test_table")
    with pytest.raises(Exception):
        await conn.execute_query("SELECT * FROM test_rename")


def test_forward_sql_postgres():
    """Test SQL generation for PostgreSQL dialect."""
    state = State("tests")
    state.apply_operation(
        CreateModel(
            model="tests.TestModel",
            table="test_rename_sql",
            fields={
                "id": fields.IntField(primary_key=True),
                "name": fields.CharField(max_length=100),
            },
        )
    )

    operation = RenameModel(
        model="tests.TestModel",
        new_table_name="renamed_table",
    )

    sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert sql == "ALTER TABLE test_rename_sql RENAME TO renamed_table"


def test_forward_sql_sqlite():
    """Test SQL generation for SQLite dialect."""
    state = State("tests")
    state.apply_operation(
        CreateModel(
            model="tests.TestModel",
            table="test_rename_sql",
            fields={
                "id": fields.IntField(primary_key=True),
                "name": fields.CharField(max_length=100),
            },
        )
    )

    operation = RenameModel(
        model="tests.TestModel",
        new_table_name="renamed_table",
    )

    sql = operation.forward_sql(state=state, schema_manager=SqliteSchemaManager())
    assert sql == "ALTER TABLE test_rename_sql RENAME TO renamed_table"


def test_invalid_rename():
    """Test that RenameModel raises ValueError when neither new_model_name nor new_table_name is provided."""
    with pytest.raises(ValueError, match="new_model_name or new_table_name must be provided"):
        RenameModel(model="tests.TestModel")


def test_backward_sql():
    """Test backward SQL generation for PostgreSQL dialect."""
    state = State("tests")
    state.apply_operation(
        CreateModel(
            model="tests.TestModel",
            table="test_rename_sql",
            fields={
                "id": fields.IntField(primary_key=True),
                "name": fields.CharField(max_length=100),
            },
        )
    )
    state.snapshot("test_backward_sql_0")

    operation = RenameModel(
        model="tests.TestModel",
        new_table_name="renamed_table",
    )
    state.apply_operation(operation)
    state.snapshot("test_backward_sql_1")

    sql = operation.backward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert sql == "ALTER TABLE renamed_table RENAME TO test_rename_sql"
