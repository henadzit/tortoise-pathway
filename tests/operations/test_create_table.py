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
    await conn.execute_query("SELECT id, name, description FROM test_create")

    # Test forward_sql and backward_sql methods
    forward_sql = operation.forward_sql(state=state)
    assert "CREATE TABLE" in forward_sql
    assert "test_create" in forward_sql

    backward_sql = operation.backward_sql(state=state)
    assert "DROP TABLE test_create" in backward_sql


class TestSqliteDialect:
    def test_forward_sql_basic_fields(self):
        """Test SQL generation for basic field types."""
        state = State("test")

        fields_dict = {
            "id": fields.IntField(primary_key=True),
            "name": fields.CharField(max_length=100),
            "description": fields.TextField(null=True),
            "is_active": fields.BooleanField(default=True),
            "created_at": fields.DatetimeField(auto_now_add=True),
            "score": fields.FloatField(null=True),
        }

        operation = CreateModel(
            model="tests.models.TestModel",
            fields=fields_dict,
        )
        operation.set_table_name("test_table")

        # Test SQLite dialect
        sql = operation.forward_sql(state=state, dialect="sqlite")

        assert (
            sql
            == """CREATE TABLE "test_table" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    score REAL
);"""
        )

    def test_forward_sql_field_constraints(self):
        """Test SQL generation with various field constraints."""
        state = State("test")

        fields_dict = {
            "id": fields.IntField(primary_key=True),
            "username": fields.CharField(max_length=50, unique=True),
            "email": fields.CharField(max_length=100, null=True, unique=True),
            "age": fields.IntField(default=18),
            "bio": fields.TextField(default="New user"),
        }

        operation = CreateModel(
            model="tests.models.TestModel",
            fields=fields_dict,
        )
        operation.set_table_name("test_constraints")

        sql = operation.forward_sql(state=state)

        assert (
            sql
            == """CREATE TABLE "test_constraints" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    age INT NOT NULL DEFAULT 18,
    bio TEXT NOT NULL DEFAULT 'New user'
);"""
        )

    def test_forward_sql_foreign_key(self):
        """Test SQL generation with foreign key fields."""
        state = State("test", schema={"models": {"User": {"table": "users", "app": "tests"}}})

        # Create model with a foreign key
        fields_dict = {
            "id": fields.IntField(primary_key=True),
            "title": fields.CharField(max_length=100),
            "user": fields.ForeignKeyField("tests.User", related_name="posts"),
        }

        operation = CreateModel(
            model="tests.models.Post",
            fields=fields_dict,
        )
        operation.set_table_name("posts")

        sql = operation.forward_sql(state=state)

        assert (
            sql
            == """CREATE TABLE "posts" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(100) NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES "users" (id)
);"""
        )


class TestPostgresDialect:
    def test_forward_sql(self):
        """Test SQL generation with PostgreSQL dialect."""
        state = State("test")

        fields_dict = {
            "id": fields.IntField(primary_key=True),
            "name": fields.CharField(max_length=100),
            "data": fields.JSONField(),
        }

        operation = CreateModel(
            model="tests.models.TestModel",
            fields=fields_dict,
        )
        operation.set_table_name("test_postgres")

        sql = operation.forward_sql(state=state, dialect="postgres")

        assert (
            sql
            == """CREATE TABLE "test_postgres" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    data JSONB NOT NULL
);"""
        )
