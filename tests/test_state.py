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
    state = State("test_app")
    assert state.schema == {"models": {}}


async def test_apply_create_model():
    """Test applying a CreateModel operation to the state."""
    state = State("test_app")

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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_add_field():
    """Test applying an AddField operation to the state."""
    state = State("test_app")

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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_drop_field():
    """Test applying a DropField operation to the state."""
    state = State("test_app")

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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_alter_field():
    """Test applying an AlterField operation to the state."""
    state = State("test_app")

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
                        "field_object": new_name_field,
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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_rename_field():
    """Test applying a RenameField operation to the state."""
    state = State("test_app")

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
                    "title": {
                        "column": "name",  # The column name doesn't change, just the field name
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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_rename_model():
    """Test applying a RenameModel operation to the state."""
    state = State("test_app")

    # First create a table
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test_app.OldModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now rename the model
    rename_model_op = RenameModel(
        model="test_app.OldModel",
        new_name="new_model",
    )

    state.apply_operation(rename_model_op)

    # Define the expected state
    expected_state = {
        "models": {
            "OldModel": {  # The model name in the state doesn't change
                "table": "new_model",  # But the table name does
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

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_get_schema():
    """Test getting the schema from the state."""
    state = State("test_app")

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

    # Get the schema
    schema = state.get_schema()

    # Define the expected schema
    expected_schema = {
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

    # Compare the schema to the expected schema
    assert schema == expected_schema


async def test_get_models():
    """Test getting the models from the state."""
    state = State("test_app")

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

    # Get the models
    models = state.get_models()

    # Define the expected models
    expected_models = {
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
        }
    }

    # Compare the models to the expected models
    assert models == expected_models


async def test_get_table_name():
    """Test getting the table name from the state."""
    state = State("test_app")

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

    # Get the table name
    table_name = state.get_table_name("TestModel")

    # Compare the table name to the expected table name
    assert table_name == "test_model"


async def test_get_column_name():
    """Test getting the column name from the state."""
    state = State("test_app")

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

    # Get the column name
    column_name = state.get_column_name("TestModel", "name")

    # Compare the column name to the expected column name
    assert column_name == "name"


async def test_ignore_operations_for_different_app():
    """Test that operations for different app are ignored."""
    state = State("test_app")

    # Create a model for a different app
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="other_app.TestModel",
        fields=fields,
    )

    # Apply the operation to the state
    state.apply_operation(create_model_op)

    # State should be empty as the operation was for a different app
    assert state.schema == {"models": {}}
