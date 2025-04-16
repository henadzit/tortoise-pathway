import pytest
from tortoise import Tortoise, fields

from tortoise_pathway.operations import CreateModel, DropModel
from tortoise_pathway.state import State


async def test_drop_table(setup_test_db):
    """Test DropModel operation."""
    state = State("test")

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.models.TestModel",
        fields=fields_dict,
    )
    # Set table name manually for test
    create_op.set_table_name("test_drop")
    await create_op.apply(state=state)

    # Verify table exists
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT * FROM test_drop")

    # Drop the table
    operation = DropModel(model="tests.models.TestModel")
    # Set table name manually for test
    operation.set_table_name("test_drop")
    await operation.apply(state=state)

    # Verify table was dropped
    with pytest.raises(Exception):
        await conn.execute_query("SELECT * FROM test_drop")

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state)
    assert "DROP TABLE test_drop" in forward_sql
