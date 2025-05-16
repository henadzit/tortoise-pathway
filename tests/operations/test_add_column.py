"""
Tests for AddField operation.
"""

from tortoise import Tortoise, fields
from tortoise_pathway.operations import CreateModel, AddField
from tortoise_pathway.schema.postgres import PostgresSchemaManager
from tortoise_pathway.state import State


async def test_add_column(setup_test_db):
    """Test AddField operation."""
    state = State("tests")

    create_op = CreateModel(
        model="tests.TestModel",
        table="test_add_column",
        fields={
            "id": fields.IntField(primary_key=True),
            "name": fields.CharField(max_length=100),
        },
    )
    await create_op.apply(state=state)
    state.apply_operation(create_op)

    # Add a column
    field = fields.IntField(default=0)
    operation = AddField(
        model="tests.TestModel",
        field_object=field,
        field_name="int_field",
    )
    await operation.apply(state=state)

    # Verify column was added
    conn = Tortoise.get_connection("default")
    await conn.execute_query("SELECT int_field from test_add_column")

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state, schema_manager=PostgresSchemaManager())
    assert "ALTER TABLE test_add_column ADD COLUMN int_field" in forward_sql
