"""
Tests for AddIndex operation.
"""

from tortoise import Tortoise, fields
from tortoise_pathway.operations import CreateModel, AddIndex
from tortoise_pathway.state import State


async def test_add_index(setup_test_db):
    """Test AddIndex operation."""
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
    create_op.set_table_name("test_add_index")
    await create_op.apply(state=state)

    # Add an index
    operation = AddIndex(
        model="tests.models.TestModel",
        field_name="name",
    )
    # Set table name manually for test
    operation.set_table_name("test_add_index")
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
