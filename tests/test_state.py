"""
Tests for the State class.
"""


from tortoise.fields import IntField, CharField, TextField, DatetimeField

from tortoise_pathway.state import State
from tortoise_pathway.operations import (
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
                "fields": fields,
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

    # Define the expected state with the new field added
    expected_fields = {
        "id": fields["id"],
        "name": fields["name"],
        "email": email_field,
    }

    expected_state = {
        "models": {
            "TestModel": {
                "table": "test_model",
                "fields": expected_fields,
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

    # Define the expected state with the field removed
    expected_fields = {
        "id": fields["id"],
        "name": fields["name"],
    }

    expected_state = {
        "models": {
            "TestModel": {
                "table": "test_model",
                "fields": expected_fields,
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

    # Define the expected state with the altered field
    expected_fields = {
        "id": fields["id"],
        "name": new_name_field,
        "created_at": fields["created_at"],
    }

    expected_state = {
        "models": {
            "TestModel": {
                "table": "test_model",
                "fields": expected_fields,
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
        "description": TextField(),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now rename a field
    rename_field_op = RenameField(
        model="test_app.TestModel",
        field_name="description",
        new_name="details",
    )

    state.apply_operation(rename_field_op)

    # Define the expected state
    expected_fields = {
        "id": fields["id"],
        "name": fields["name"],
        "details": fields["description"],
    }

    expected_state = {
        "models": {
            "TestModel": {
                "table": "test_model",
                "fields": expected_fields,
                "indexes": [],
            },
        }
    }

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_apply_rename_model():
    """Test applying a RenameModel operation to the state."""
    state = State("test_app")

    # First create a model
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Now rename the model's table
    rename_model_op = RenameModel(
        model="test_app.TestModel",
        new_name="new_test_model",
    )

    state.apply_operation(rename_model_op)

    # Define the expected state
    expected_state = {
        "models": {
            "TestModel": {
                "table": "new_test_model",  # Table name changed
                "fields": fields,
                "indexes": [],
            },
        }
    }

    # Compare the entire state schema to the expected state
    assert state.schema == expected_state


async def test_get_schema():
    """Test getting the schema."""
    state = State("test_app")

    # Create a model
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

    # Define the expected state
    expected_state = {
        "models": {
            "TestModel": {
                "table": "test_model",
                "fields": fields,
                "indexes": [],
            },
        }
    }

    # Compare the schema to the expected state
    assert schema == expected_state


async def test_get_models():
    """Test getting the models."""
    state = State("test_app")

    # Create a model
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
            "fields": fields,
            "indexes": [],
        },
    }

    # Compare the models to the expected models
    assert models == expected_models


async def test_get_table_name():
    """Test getting a table name."""
    state = State("test_app")

    # Create a model
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

    # Verify the table name
    assert table_name == "test_model"


async def test_get_column_name():
    """Test getting a column name."""
    state = State("test_app")

    # Create a model with a field having source_field
    id_field = IntField(primary_key=True)
    name_field = CharField(max_length=100)

    # Create field with explicit source_field attribute
    custom_field = CharField(max_length=50)
    setattr(custom_field, "source_field", "custom_column")

    fields = {
        "id": id_field,
        "name": name_field,
        "custom": custom_field,
    }

    create_model_op = CreateModel(
        model="test_app.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Get the column names
    id_column = state.get_column_name("TestModel", "id")
    name_column = state.get_column_name("TestModel", "name")
    custom_column = state.get_column_name("TestModel", "custom")

    # Verify the column names
    assert id_column == "id"  # Default column name
    assert name_column == "name"  # Default column name
    assert custom_column == "custom_column"  # Custom column name from source_field


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
