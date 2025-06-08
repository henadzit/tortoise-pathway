"""
Tests for RunSQL operation.
"""

from tortoise import Tortoise, fields
from tortoise_pathway.operations import CreateModel, RunSQL
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.state import State


async def test_run_sql_basic(setup_test_db):
    """Test RunSQL operation with basic SQL statements."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_run_sql",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Insert a row using RunSQL
    insert_sql = "INSERT INTO test_run_sql (id, name) VALUES (1, 'test_value')"
    delete_sql = "DELETE FROM test_run_sql WHERE id = 1"

    run_sql_op = RunSQL(
        forward_sql=insert_sql,
        backward_sql=delete_sql,
    )

    # Test SQL generation
    forward_sql = run_sql_op.forward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert forward_sql == insert_sql

    backward_sql = run_sql_op.backward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert backward_sql == delete_sql

    # Apply the operation
    await run_sql_op.apply(state=state)

    # Verify data was inserted
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query("SELECT * FROM test_run_sql WHERE id = 1")
    rows = result[1]
    assert len(rows) == 1
    assert rows[0]["name"] == "test_value"

    # Revert the operation
    await run_sql_op.revert(state=state)

    # Verify data was deleted
    result = await conn.execute_query("SELECT * FROM test_run_sql WHERE id = 1")
    rows = result[1]
    assert len(rows) == 0


async def test_run_sql_multiline(setup_test_db):
    """Test RunSQL operation with multi-line SQL statements."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_run_sql_multi",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Multi-line SQL
    forward_sql = """
    INSERT INTO test_run_sql_multi (id, name) VALUES (1, 'value1');
    INSERT INTO test_run_sql_multi (id, name) VALUES (2, 'value2');
    INSERT INTO test_run_sql_multi (id, name) VALUES (3, 'value3');
    """

    backward_sql = """
    DELETE FROM test_run_sql_multi WHERE id IN (1, 2, 3);
    """

    run_sql_op = RunSQL(
        forward_sql=forward_sql,
        backward_sql=backward_sql,
    )

    # Apply the operation
    await run_sql_op.apply(state=state)

    # Verify data was inserted
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query("SELECT COUNT(*) as count FROM test_run_sql_multi")
    count = result[1][0]["count"]
    assert count == 3

    # Revert the operation
    await run_sql_op.revert(state=state)

    # Verify data was deleted
    result = await conn.execute_query("SELECT COUNT(*) as count FROM test_run_sql_multi")
    count = result[1][0]["count"]
    assert count == 0


async def test_run_sql_no_backward(setup_test_db):
    """Test RunSQL operation with no backward SQL."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_run_sql_no_backward",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # SQL with no backward statement
    expected_forward_sql = "INSERT INTO test_run_sql_no_backward (id, name) VALUES (1, 'test_value')"

    run_sql_op = RunSQL(
        forward_sql=expected_forward_sql,
        backward_sql=None,
    )

    # Test SQL generation
    forward_sql = run_sql_op.forward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert forward_sql == expected_forward_sql

    backward_sql = run_sql_op.backward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert backward_sql == ""

    # Apply the operation
    await run_sql_op.apply(state=state)

    # Verify data was inserted
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query("SELECT * FROM test_run_sql_no_backward WHERE id = 1")
    rows = result[1]
    assert len(rows) == 1
    assert rows[0]["name"] == "test_value"


def test_to_migration():
    """Test generating migration code for RunSQL operations."""
    # Simple SQL
    simple_op = RunSQL(
        forward_sql="INSERT INTO table VALUES (1, 'test')",
        backward_sql="DELETE FROM table WHERE id = 1",
    )

    migration_code = simple_op.to_migration()
    assert "forward_sql=\"INSERT INTO table VALUES (1, 'test')\"" in migration_code
    assert 'backward_sql="DELETE FROM table WHERE id = 1"' in migration_code

    # Multi-line SQL
    multi_op = RunSQL(
        forward_sql="INSERT INTO table VALUES (1, 'test');\nINSERT INTO table VALUES (2, 'test2');",
        backward_sql=None,
    )

    migration_code = multi_op.to_migration()
    assert 'forward_sql="""' in migration_code
    assert "INSERT INTO table VALUES (1, 'test');\nINSERT INTO table VALUES (2, 'test2');" in migration_code
    assert "backward_sql=None" in migration_code
