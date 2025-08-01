"""
Tests for DropIndex operation.
"""

from tortoise import Tortoise, fields
from tortoise.indexes import Index
from tortoise_pathway.operations import CreateModel, AddIndex, DropIndex
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.state import State


async def test_drop_index(setup_test_db):
    """Test DropIndex operation."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_drop_index",
        fields=fields_dict,
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Add an index
    add_index_op = AddIndex(
        model="tests.TestModel",
        index=Index(name="idx_test_model_name", fields=["name"]),
    )
    await add_index_op.apply(state=state)
    state.apply_operation(add_index_op)

    state.snapshot("index_added")

    # Verify index exists
    conn = Tortoise.get_connection("default")
    if conn.capabilities.dialect == "sqlite":
        indices = await conn.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
        )
        index_names = [index["name"] for index in indices[1]]
        assert "idx_test_model_name" in index_names

    # Drop the index
    operation = DropIndex(
        model="tests.TestModel",
        index_name="idx_test_model_name",
    )

    # Test SQL generation
    forward_sql = operation.forward_sql(
        state=state, schema_manager=PostgresSchemaManager()
    )
    assert "DROP INDEX" in forward_sql

    await operation.apply(state=state)
    state.apply_operation(operation)

    state.snapshot("index_dropped")

    backward_sql = operation.backward_sql(
        state=state, schema_manager=PostgresSchemaManager()
    )
    assert "CREATE INDEX" in backward_sql

    # Verify index was dropped
    if conn.capabilities.dialect == "sqlite":
        indices = await conn.execute_query(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
        )
        index_names = [index["name"] for index in indices[1]]
        assert "idx_test_model_name" not in index_names
