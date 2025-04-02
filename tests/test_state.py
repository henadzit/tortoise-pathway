"""
Tests for the State class.
"""


from tortoise.fields import IntField, CharField, TextField, DatetimeField

from tortoise_pathway.state import State
from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import (
    CreateModel,
    AddField,
    DropField,
    AlterField,
    RenameField,
    RenameModel,
)


async def test_build_empty_state():
    """Test building an empty state."""
    state = State()
    assert state.schemas == {}


async def test_apply_create_model():
    """Test applying a CreateModel operation to the state."""
    state = State()

    # Create a model schema that would be used in a migration
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "description": TextField(),
    }

    # Create a migration operation
    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    # Apply the operation to the state
    state.apply_operation(create_model_op)

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


async def test_apply_add_field():
    """Test applying an AddField operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now add a field
    email_field = CharField(max_length=255)
    add_field_op = AddField(
        model="test_app.TestModel",
        field_object=email_field,
        field_name="email",
    )

    state.apply_operation(add_field_op)

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


async def test_apply_drop_field():
    """Test applying a DropField operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "email": CharField(max_length=255),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now drop a field
    drop_field_op = DropField(
        model="test_app.TestModel",
        field_name="email",
    )

    state.apply_operation(drop_field_op)

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


async def test_apply_alter_field():
    """Test applying an AlterField operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now alter a field
    new_name_field = CharField(max_length=200)  # Changed max_length from 100 to 200
    alter_field_op = AlterField(
        model="test_app.TestModel",
        field_object=new_name_field,
        field_name="name",
    )

    state.apply_operation(alter_field_op)

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
                            "column": "name",  # Column name stays the same
                            "type": "CharField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": new_name_field,  # But field object is updated
                        },
                        "created_at": {
                            "column": "created_at",
                            "type": "DatetimeField",
                            "nullable": False,
                            "default": None,
                            "primary_key": False,
                            "field_object": fields["created_at"],
                        },
                    },
                    "indexes": [],
                },
            }
        }
    }

    # Compare the entire state.schemas to the expected state
    assert state.schemas == expected_state


async def test_apply_rename_field():
    """Test applying a RenameField operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now rename a field
    rename_field_op = RenameField(
        model="test_app.TestModel",
        field_name="name",
        new_name="title",
    )

    state.apply_operation(rename_field_op)

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
                        "title": {  # Field name is now 'title' instead of 'name'
                            "column": "name",  # But column name remains 'name'
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


async def test_apply_rename_model():
    """Test applying a RenameModel operation to the state."""
    state = State()

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now rename the table
    rename_model_op = RenameModel(
        model="test_app.TestModel",
        new_name="posts",  # New table name
    )

    state.apply_operation(rename_model_op)

    # Define the expected state
    expected_state = {
        "test_app": {
            "models": {
                "TestModel": {  # The model name in state remains TestModel
                    "table": "posts",  # But the table name is updated to 'posts'
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

    create_model_op1 = CreateModel(
        model="auth.User",
        fields=fields1,
    )

    fields2 = {
        "id": IntField(primary_key=True),
        "title": CharField(max_length=200),
        "content": TextField(),
    }

    create_model_op2 = CreateModel(
        model="blog.Article",
        fields=fields2,
    )

    state.apply_operation(create_model_op1)
    state.apply_operation(create_model_op2)

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
