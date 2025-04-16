"""
Tests for CreateModel operation.
"""

from tortoise import Tortoise, fields
from tortoise_pathway.operations import CreateModel
from tortoise_pathway.state import State


async def test_create_table(setup_test_db):
    """Test CreateModel operation."""
    state = State("test")

    # Create fields dictionary
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
        "description": fields.TextField(null=True),
    }

    # Create and apply operation
    operation = CreateModel(
        model="tests.models.TestModel",
        fields=fields_dict,
    )
    # Set table name manually to override automatic name derivation
    operation.set_table_name("test_create")
    await operation.apply(state=state)

    # Verify table was created
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_create'"
    )
    assert len(result[1]) == 1

    # Verify table has the expected columns
    columns = await conn.execute_query("PRAGMA table_info(test_create)")
    column_names = [column["name"] for column in columns[1]]
    assert "id" in column_names
    assert "name" in column_names
    assert "description" in column_names

    # Test forward_sql and backward_sql methods
    forward_sql = operation.forward_sql(state=state)
    assert "CREATE TABLE" in forward_sql
    assert "test_create" in forward_sql

    backward_sql = operation.backward_sql(state=state)
    assert "DROP TABLE test_create" in backward_sql
