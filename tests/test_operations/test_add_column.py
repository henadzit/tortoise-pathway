"""
Tests for AddField operation.
"""

from tortoise import Tortoise, fields
from tortoise_pathway.operations import CreateModel, AddField
from tortoise_pathway.state import State


async def test_add_column(setup_test_db):
    """Test AddField operation."""
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
    create_op.set_table_name("test_add_column")
    await create_op.apply(state=state)

    # Add a column
    field = fields.IntField(default=0)
    operation = AddField(
        model="tests.models.TestModel",
        field_object=field,
        field_name="count",
    )
    # Set table name manually for test
    operation.set_table_name("test_add_column")
    await operation.apply(state=state)

    # Verify column was added
    conn = Tortoise.get_connection("default")
    columns = await conn.execute_query("PRAGMA table_info(test_add_column)")
    column_names = [column["name"] for column in columns[1]]
    assert "count" in column_names

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state)
    assert "ALTER TABLE test_add_column ADD COLUMN count" in forward_sql
