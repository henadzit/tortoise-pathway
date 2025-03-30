"""
Tests for schema change operations.
"""

import pytest

from tortoise import Tortoise, fields, models
from tortoise_pathway.schema_change import (
    CreateTable,
    DropTable,
    AddColumn,
    AddIndex,
    DropIndex,
)


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
    """Test CreateTable operation."""
    # Create fields dictionary
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
        "description": fields.TextField(null=True),
    }

    # Create and apply operation
    operation = CreateTable(
        table_name="test_create",
        fields=fields_dict,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await operation.apply()

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
    forward_sql = operation.forward_sql()
    assert "CREATE TABLE" in forward_sql
    assert "test_create" in forward_sql

    backward_sql = operation.backward_sql()
    assert "DROP TABLE test_create" in backward_sql


async def test_drop_table(setup_test_db):
    """Test DropTable operation."""
    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateTable(
        table_name="test_drop",
        fields=fields_dict,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await create_op.apply()

    # Verify table exists
    conn = Tortoise.get_connection("default")
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_drop'"
    )
    assert len(result[1]) == 1

    # Drop the table
    operation = DropTable(
        table_name="test_drop", model="tests.test_operations.test_schema_diff.TestModel"
    )
    await operation.apply()

    # Verify table was dropped
    result = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='test_drop'"
    )
    assert len(result[1]) == 0

    # Test SQL generation
    forward_sql = operation.forward_sql()
    assert "DROP TABLE test_drop" in forward_sql


async def test_add_column(setup_test_db):
    """Test AddColumn operation."""
    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateTable(
        table_name="test_add_column",
        fields=fields_dict,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await create_op.apply()

    # Add a column
    field = fields.IntField(default=0)
    operation = AddColumn(
        table_name="test_add_column",
        column_name="count",
        field_object=field,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await operation.apply()

    # Verify column was added
    conn = Tortoise.get_connection("default")
    columns = await conn.execute_query("PRAGMA table_info(test_add_column)")
    column_names = [column["name"] for column in columns[1]]
    assert "count" in column_names

    # Test SQL generation
    forward_sql = operation.forward_sql()
    assert "ALTER TABLE test_add_column ADD COLUMN count" in forward_sql


async def test_add_index(setup_test_db):
    """Test AddIndex operation."""
    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateTable(
        table_name="test_add_index",
        fields=fields_dict,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await create_op.apply()

    # Add an index
    operation = AddIndex(
        table_name="test_add_index",
        column_name="name",
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await operation.apply()

    # Verify index was added (for SQLite)
    conn = Tortoise.get_connection("default")
    indices = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_add_index'"
    )
    index_names = [index["name"] for index in indices[1]]
    assert "idx_test_add_index_name" in index_names

    # Test SQL generation
    forward_sql = operation.forward_sql()
    assert "CREATE INDEX" in forward_sql
    assert "test_add_index" in forward_sql
    assert "name" in forward_sql

    backward_sql = operation.backward_sql()
    assert "DROP INDEX" in backward_sql


async def test_drop_index(setup_test_db):
    """Test DropIndex operation."""
    # First create a table
    fields_dict = {
        "id": fields.IntField(primary_key=True),
        "name": fields.CharField(max_length=100),
    }

    create_op = CreateTable(
        table_name="test_drop_index",
        fields=fields_dict,
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await create_op.apply()

    # Add an index
    add_index_op = AddIndex(
        table_name="test_drop_index",
        column_name="name",
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await add_index_op.apply()

    # Verify index exists
    conn = Tortoise.get_connection("default")
    indices = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
    )
    index_names = [index["name"] for index in indices[1]]
    assert "idx_test_drop_index_name" in index_names

    # Drop the index
    operation = DropIndex(
        table_name="test_drop_index",
        column_name="name",
        model="tests.test_operations.test_schema_diff.TestModel",
    )
    await operation.apply()

    # Verify index was dropped
    indices = await conn.execute_query(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='test_drop_index'"
    )
    index_names = [index["name"] for index in indices[1]]
    assert "idx_test_drop_index_name" not in index_names

    # Test SQL generation
    forward_sql = operation.forward_sql()
    assert "DROP INDEX" in forward_sql

    backward_sql = operation.backward_sql()
    assert "CREATE INDEX" in backward_sql
