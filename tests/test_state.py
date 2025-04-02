"""
Tests for the State class.
"""


from tortoise.fields import IntField, CharField, TextField, DatetimeField

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
        model="test_app.TestModel",
        fields=fields,
    )

    # Apply the operation to the state
    state.apply_operation(create_table_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                        "description": {
                            "column": "description",
                            "type": "TextField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["description"],
                        },
                    },
                    "indexes": [],
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
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_table_op)

    # Now add a column
    email_field = CharField(max_length=255)
    add_column_op = AddColumn(
        model="test_app.TestModel",
        field_object=email_field,
        field_name="email",
    )

    state.apply_operation(add_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                        "email": {
                            "column": "email",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": email_field,
                        },
                    },
                    "indexes": [],
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
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_table_op)

    # Now drop a column
    drop_column_op = DropColumn(
        model="test_app.TestModel",
        field_name="email",
    )

    state.apply_operation(drop_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
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
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_table_op)

    # Now alter a column (make it nullable)
    altered_field = CharField(max_length=100, null=True)
    alter_column_op = AlterColumn(
        model="test_app.TestModel",
        column_name="name",
        field_object=altered_field,
        field_name="name",
    )

    state.apply_operation(alter_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": True,
                            "default": None,
                            "primary_key": False,
                            "field_object": altered_field,
                        },
                    },
                    "indexes": [],
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
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_table_op)

    # Now rename a column
    rename_column_op = RenameColumn(
        model="test_app.TestModel",
        column_name="name",
        new_name="title",
    )

    state.apply_operation(rename_column_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "title",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
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
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_table_op)

    # Now rename the table
    rename_table_op = RenameTable(
        model="test_app.TestModel",
        new_name="new_table",
    )

    state.apply_operation(rename_table_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {
                    "table": "new_table",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["name"],
                        },
                    },
                    "indexes": [],
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_get_schema():
    """Test getting the schema from the state."""
    state = State()

    # Add some tables in different apps
    fields1 = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_table_op1 = CreateTable(
        model="auth.User",
        fields=fields1,
    )

    fields2 = {
        "id": IntField(primary_key=True),
        "title": CharField(max_length=200),
        "content": TextField(),
    }

    create_table_op2 = CreateTable(
        model="blog.Article",
        fields=fields2,
    )

    state.apply_operation(create_table_op1)
    state.apply_operation(create_table_op2)

    # Get the schema
    schema = state.get_schema()

    # Define the expected schema
    expected_schema = {
        "auth": {
            "models": {
                "User": {
                    "table": "user",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields1["id"],
                        },
                        "name": {
                            "column": "name",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields1["name"],
                        },
                    },
                    "indexes": [],
                }
            }
        },
        "blog": {
            "models": {
                "Article": {
                    "table": "article",
                    "fields": {
                        "id": {
                            "column": "id",
                            "type": "IntField",
                            "nullable": False,
                            "default": None,
                            "primary_key": True,
                            "field_object": fields2["id"],
                        },
                        "title": {
                            "column": "title",
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields2["title"],
                        },
                        "content": {
                            "column": "content",
                            "type": "TextField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields2["content"],
                        },
                    },
                    "indexes": [],
                }
            }
        },
    }

    # Compare the schema to the expected schema
    assert schema == expected_schema
