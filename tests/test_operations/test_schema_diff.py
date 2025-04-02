"""
Tests for schema change operations.
"""

import pytest

from tortoise import Tortoise, fields, models
from tortoise_pathway.schema_change import (
    CreateModel,
    DropModel,
    AddField,
    AddIndex,
    DropIndex,
)
from tortoise_pathway.state import State


class TestModel(models.Model):
    """Test model for schema operations."""

    __test__ = False

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)

    class Meta:
        table = "test_table"


@pytest.fixture
async def setup_test_db(setup_db_file):
    """Set up a test database with Tortoise ORM."""
    config = {
        "connections": {
            "default": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": str(setup_db_file)},
            },
        },
        "apps": {
            "test": {
                "models": ["tests.test_operations.test_schema_diff"],
                "default_connection": "default",
            }
        },
    }

    await Tortoise.init(config=config)
    yield
    await Tortoise.close_connections()


async def test_create_table(setup_test_db):
    """Test CreateModel operation."""
    state = State()

    # Create fields dictionary
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
        "description": fields.TextField(null=True),
    }

    # Create and apply operation
    operation = CreateModel(
        model="tests.test_operations.test_schema_diff.TestModel",
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


async def test_drop_table(setup_test_db):
    """Test DropModel operation."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.test_operations.test_schema_diff.TestModel",
        fields=fields_dict,
    )
    # Set table name manually for test
    create_op.set_table_name("test_drop")
    await create_op.apply(state=state)

    # Verify table exists
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_drop'"
    )
    assert len(result[1]) == 1

    # Drop the table
    operation = DropModel(model="tests.test_operations.test_schema_diff.TestModel")
    # Set table name manually for test
    operation.set_table_name("test_drop")
    await operation.apply(state=state)

    # Verify table was dropped
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_drop'"
    )
    assert len(result[1]) == 0

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state)
    assert "DROP TABLE test_drop" in forward_sql


async def test_add_column(setup_test_db):
    """Test AddField operation."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.test_operations.test_schema_diff.TestModel",
        fields=fields_dict,
    )
    # Set table name manually for test
    create_op.set_table_name("test_add_column")
    await create_op.apply(state=state)

    # Add a column
    field = fields.IntField(default=0)
    operation = AddField(
        model="tests.test_operations.test_schema_diff.TestModel",
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


async def test_add_index(setup_test_db):
    """Test AddIndex operation."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.test_operations.test_schema_diff.TestModel",
        fields=fields_dict,
    )
    # Set table name manually for test
    create_op.set_table_name("test_add_index")
    await create_op.apply(state=state)

    # Add an index
    operation = AddIndex(
        model="tests.test_operations.test_schema_diff.TestModel",
        field_name="name",
    )
    # Set table name manually for test
    operation.set_table_name("test_add_index")
    await operation.apply(state=state)

    # Verify index was added (for SQLite)
    conn = Tortoise.get_connection("default")
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


async def test_drop_index(setup_test_db):
    """Test DropIndex operation."""
    state = State()

    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateModel(
        model="tests.test_operations.test_schema_diff.TestModel",
        fields=fields_dict,
    )
    # Set table name manually for test
    create_op.set_table_name("test_drop_index")
    await create_op.apply(state=state)

    # Add an index
    add_index_op = AddIndex(
        model="tests.test_operations.test_schema_diff.TestModel",
        field_name="name",
    )
    # Set table name manually for test
    add_index_op.set_table_name("test_drop_index")
    await add_index_op.apply(state=state)

    # Verify index exists
    conn = Tortoise.get_connection("default")
    indices = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
    )
    index_names = [index["name"] for index in indices[1]]
    assert "idx_test_model_name" in index_names

    # Drop the index
    operation = DropIndex(
        model="tests.test_operations.test_schema_diff.TestModel",
        field_name="name",
    )
    # Set table name manually for test
    operation.set_table_name("test_drop_index")
    await operation.apply(state=state)

    # Verify index was dropped
    indices = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
    )
    index_names = [index["name"] for index in indices[1]]
    assert "idx_test_model_name" not in index_names

    # Test SQL generation
    forward_sql = operation.forward_sql(state=state)
    assert "DROP INDEX" in forward_sql

    backward_sql = operation.backward_sql(state=state)
    assert "CREATE INDEX" in backward_sql
