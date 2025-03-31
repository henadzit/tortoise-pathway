"""
Tests for the State class.
"""

import pytest

from tortoise.fields import IntField, CharField, TextField, DatetimeField
from tortoise.models import Model

from tortoise_pathway.state import State
from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import (
    CreateTable,
    AddColumn,
    DropColumn,
    AlterColumn,
    RenameColumn,
    RenameTable,
)


async def test_build_empty_state():
    """Test building an empty state."""
    state = State()
    assert state.schemas == {}


async def test_apply_create_table():
    """Test applying a CreateTable operation to the state."""
    state = State()

    # Create a model schema that would be used in a migration
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "description": TextField(),
    }

    # Create a migration operation
    create_table_op = CreateTable(
        table_name="test_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    # Apply the operation to the state
    state._apply_operation(create_table_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "test_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                        "description": {
                            "field_name": "description",
                            "type": "TextField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["description"],
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_add_column():
    """Test applying an AddColumn operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op = CreateTable(
        table_name="test_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    state._apply_operation(create_table_op)

    # Now add a column
    email_field = CharField(max_length=255)
    add_column_op = AddColumn(
        table_name="test_table",
        column_name="email",
        field_object=email_field,
        model="test_app.TestModel",
        params={"field_name": "email"},
    )

    state._apply_operation(add_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "test_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                        "email": {
                            "field_name": "email",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": email_field,
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_drop_column():
    """Test applying a DropColumn operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "email": CharField(max_length=255),
    }

    create_table_op = CreateTable(
        table_name="test_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    state._apply_operation(create_table_op)

    # Now drop a column
    drop_column_op = DropColumn(
        table_name="test_table",
        column_name="email",
        model="test_app.TestModel",
    )

    state._apply_operation(drop_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "test_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_alter_column():
    """Test applying an AlterColumn operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op = CreateTable(
        table_name="test_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    state._apply_operation(create_table_op)

    # Now alter a column (make it nullable)
    altered_field = CharField(max_length=100, null=True)
    alter_column_op = AlterColumn(
        table_name="test_table",
        column_name="name",
        field_object=altered_field,
        model="test_app.TestModel",
        params={"field_name": "name"},
    )

    state._apply_operation(alter_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "test_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": True,
                            "default": None,
                            "primary_key": False,
                            "field_object": altered_field,
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_rename_column():
    """Test applying a RenameColumn operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op = CreateTable(
        table_name="test_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    state._apply_operation(create_table_op)

    # Now rename a column
    rename_column_op = RenameColumn(
        table_name="test_table",
        column_name="name",
        new_name="title",
        model="test_app.TestModel",
    )

    state._apply_operation(rename_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "test_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "title": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_rename_table():
    """Test applying a RenameTable operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op = CreateTable(
        table_name="old_table",
        fields=fields,
        model="test_app.TestModel",
        params={},
    )

    state._apply_operation(create_table_op)

    # Now rename the table
    rename_table_op = RenameTable(
        table_name="old_table",
        new_name="new_table",
        model="test_app.TestModel",
    )

    state._apply_operation(rename_table_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "tables": {
                "new_table": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
                    "model": "test_app.TestModel",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_build_state_from_migrations():
    """Test building state from a list of migrations."""

    # Create a test migration class
    class TestMigration(Migration):
        """Test migration with a CreateTable operation."""

        dependencies = []

        def __init__(self):
            fields = {
                "id": IntField(primary_key=True),
                "name": CharField(max_length=100),
            }

            self.operations = [
                CreateTable(
                    table_name="blog_posts",
                    fields=fields,
                    model="blog.BlogPost",
                    params={},
                )
            ]

    # Create another migration that adds a column
    class AddColumnMigration(Migration):
        """Test migration with an AddColumn operation."""

        dependencies = ["test_migration"]

        def __init__(self):
            self.operations = [
                AddColumn(
                    table_name="blog_posts",
                    column_name="created_at",
                    field_object=DatetimeField(auto_now_add=True),
                    model="blog.BlogPost",
                    params={"field_name": "created_at"},
                )
            ]

    # Build state from both migrations
    state = State()
    migrations = [TestMigration(), AddColumnMigration()]
    await state.build_from_migrations(migrations)

    # Get the field objects from the migrations for the expected state
    id_field = None
    name_field = None
    created_at_field = None

    # Extract fields from the first migration (CreateTable)
    for operation in migrations[0].operations:
        if isinstance(operation, CreateTable):
            id_field = operation.fields["id"]
            name_field = operation.fields["name"]

    # Extract field from the second migration (AddColumn)
    for operation in migrations[1].operations:
        if isinstance(operation, AddColumn):
            created_at_field = operation.field_object

    # Define the expected state
    expected_state = {
        "blog": {
            "tables": {
                "blog_posts": {
                    "columns": {
                        "id": {
                            "field_name": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": id_field,
                        },
                        "name": {
                            "field_name": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": name_field,
                        },
                        "created_at": {
                            "field_name": "created_at",
                            "type": "DatetimeField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": created_at_field,
                        },
                    },
                    "indexes": [],
                    "model": "blog.BlogPost",
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_get_schema():
    """Test getting a flattened schema from the state."""
    state = State()

    # Add some tables in different apps
    fields1 = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op1 = CreateTable(
        table_name="users",
        fields=fields1,
        model="auth.User",
        params={},
    )

    fields2 = {
        "id": IntField(primary_key=True),
        "title": CharField(max_length=200),
        "content": TextField(),
    }

    create_table_op2 = CreateTable(
        table_name="articles",
        fields=fields2,
        model="blog.Article",
        params={},
    )

    state._apply_operation(create_table_op1)
    state._apply_operation(create_table_op2)

    # Get the flattened schema
    schema = state.get_schema()

    # Define the expected schema
    expected_schema = {
        "users": {
            "columns": {
                "id": {
                    "field_name": "id",
                    "type": "IntField",
                    "nullable": False,
                    "default": None,
                    "primary_key": True,
                    "field_object": fields1["id"],
                },
                "name": {
                    "field_name": "name",
                    "type": "CharField",
                    "nullable": False,
                    "default": None,
                    "primary_key": False,
                    "field_object": fields1["name"],
                },
            },
            "indexes": [],
            "model": "auth.User",
        },
        "articles": {
            "columns": {
                "id": {
                    "field_name": "id",
                    "type": "IntField",
                    "nullable": False,
                    "default": None,
                    "primary_key": True,
                    "field_object": fields2["id"],
                },
                "title": {
                    "field_name": "title",
                    "type": "CharField",
                    "nullable": False,
                    "default": None,
                    "primary_key": False,
                    "field_object": fields2["title"],
                },
                "content": {
                    "field_name": "content",
                    "type": "TextField",
                    "nullable": False,
                    "default": None,
                    "primary_key": False,
                    "field_object": fields2["content"],
                },
            },
            "indexes": [],
            "model": "blog.Article",
        },
    }

    # Compare the entire schema to the expected schema
    assert schema == expected_schema
