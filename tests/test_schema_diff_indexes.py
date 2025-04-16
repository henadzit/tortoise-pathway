"""
Tests for the SchemaDiffer's ability to detect index changes.
"""

from tortoise.fields import IntField, CharField, DatetimeField

from tortoise_pathway.state import State
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.operations import AddIndex, DropIndex, CreateModel


async def test_detect_index_additions():
    """Test detecting added indexes."""
    # Initialize state with a model without indexes
    state = State("test")

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer("test", state)

    def mock_get_model_schema():
        return {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": fields,
                    "indexes": [
                        {
                            "name": "idx_test_model_created_at",
                            "unique": False,
                            "columns": ["created_at"],
                        }
                    ],
                }
            }
        }

    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: AddIndex
    assert len(changes) == 1
    assert isinstance(changes[0], AddIndex)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"
    assert changes[0].index_name == "idx_test_model_created_at"
    assert changes[0].fields == ["created_at"]


async def test_detect_index_removals():
    """Test detecting removed indexes."""
    # Initialize state with a model with an index
    state = State("test")

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Add index to the state model
    state.schema["models"]["TestModel"]["indexes"] = [
        {"name": "idx_test_model_created_at", "unique": False, "columns": ["created_at"]}
    ]

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer("test", state)

    def mock_get_model_schema():
        return {"models": {"TestModel": {"table": "test_model", "fields": fields, "indexes": []}}}

    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: DropIndex
    assert len(changes) == 1
    assert isinstance(changes[0], DropIndex)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"
    assert changes[0].index_name == "idx_test_model_created_at"


async def test_detect_index_modifications():
    """Test detecting modified indexes (changing unique constraint)."""
    # Initialize state with a model with a non-unique index
    state = State("test")

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Add index to the state model
    state.schema["models"]["TestModel"]["indexes"] = [
        {"name": "idx_test_model_created_at", "unique": False, "columns": ["created_at"]}
    ]

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer("test", state)

    def mock_get_model_schema():
        return {
            "models": {
                "TestModel": {
                    "table": "test_model",
                    "fields": fields,
                    "indexes": [
                        {
                            "name": "idx_test_model_created_at",
                            "unique": True,  # Changed to unique
                            "columns": ["created_at"],
                        }
                    ],
                }
            }
        }

    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be two changes: DropIndex followed by AddIndex
    assert len(changes) == 2
    assert isinstance(changes[0], DropIndex)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"
    assert changes[0].index_name == "idx_test_model_created_at"

    assert isinstance(changes[1], AddIndex)
    assert changes[1].model == "test.TestModel"
    assert changes[1].field_name == "created_at"
    assert changes[1].index_name == "idx_test_model_created_at"
    assert changes[1].unique is True
