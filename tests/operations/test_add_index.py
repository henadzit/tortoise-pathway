"""
Tests for AddIndex operation.
"""

from tortoise import Tortoise, fields
from tortoise.indexes import Index
from tortoise_pathway.operations import CreateModel, AddIndex
from tortoise_pathway.state import State


async def test_add_index(setup_test_db):
    """Test AddIndex operation."""
    state = State("tests")

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_add_index",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Add an index
    operation = AddIndex(
        model="tests.TestModel",
        index=Index(name="idx_test_model_name", fields=["name"]),
    )
    await operation.apply(state=state)

    # Verify index was added (for SQLite)
    conn = Tortoise.get_connection("default")

    if conn.capabilities.dialect == "sqlite":
        indices = await conn.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_add_index'"
        )
        index_names = [index["name"] for index in indices[1]]
        assert "idx_test_model_name" in index_names

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state)
    assert "CREATE INDEX" in forward_sql
    assert "test_add_index" in forward_sql
    assert "name" in forward_sql

    backward_sql = operation.backward_sql(state=state)
    assert "DROP INDEX" in backward_sql
