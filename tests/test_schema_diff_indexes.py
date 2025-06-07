"""
Tests for the SchemaDiffer's ability to detect index changes.
"""

from tortoise.fields import IntField, CharField, DatetimeField
from tortoise.indexes import Index
from tortoise_pathway.index_ext import UniqueIndex

from tortoise_pathway.state import State, Schema
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.operations import AddIndex, DropIndex, CreateModel


async def test_detect_index_additions():
    """Test detecting added indexes."""
    # Initialize state with a model without indexes
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        table="test_model",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    def mock_get_model_schema() -> Schema:
        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": fields,
                        "indexes": [
                            Index(
                                fields=["created_at"],
                                name="idx_test_model_created_at",
                            )
                        ],
                    }
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
    assert changes[0].index.fields == ["created_at"]
    assert changes[0].index.name == "idx_test_model_created_at"
    assert not isinstance(changes[0].index, UniqueIndex)

    # check that the detected changes lead to a stable state
    state.apply_operation(changes[0])

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_index_removals():
    """Test detecting removed indexes."""
    # Initialize state with a model with an index
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }
    state.apply_operation(
        CreateModel(
            model="test.TestModel",
            table="test_model",
            fields=fields,
        )
    )
    state.apply_operation(
        AddIndex(
            model="test.TestModel",
            index=Index(
                fields=["created_at"],
                name="idx_test_model_created_at",
            ),
        )
    )

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    def mock_get_model_schema() -> Schema:
        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": fields,
                        "indexes": [],
                    }
                }
            }
        }

    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: DropIndex
    assert len(changes) == 1
    assert isinstance(changes[0], DropIndex)
    assert changes[0].model == "test.TestModel"
    assert changes[0].index_name == "idx_test_model_created_at"

    # check that the detected changes lead to a stable state
    state.apply_operation(changes[0])

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_change_to_unique():
    """Test detecting modified indexes (changing unique constraint)."""
    # Initialize state with a model with a non-unique index
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "created_at": DatetimeField(auto_now_add=True),
    }

    state.apply_operation(
        CreateModel(
            model="test.TestModel",
            table="test_model",
            fields=fields,
        )
    )
    state.apply_operation(
        AddIndex(
            model="test.TestModel",
            index=Index(
                fields=["created_at"],
                name="idx_test_model_created_at",
            ),
        )
    )

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    def mock_get_model_schema() -> Schema:
        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": fields,
                        "indexes": [
                            UniqueIndex(
                                fields=["created_at"],
                                name="idx_test_model_created_at",
                            )
                        ],
                    }
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
    assert changes[0].index_name == "idx_test_model_created_at"

    assert isinstance(changes[1], AddIndex)
    assert changes[1].model == "test.TestModel"
    assert changes[1].index.fields == ["created_at"]
    assert changes[1].index.name == "idx_test_model_created_at"
    assert isinstance(changes[1].index, UniqueIndex)

    # check that the detected changes lead to a stable state
    state.apply_operation(changes[0])
    state.apply_operation(changes[1])

    changes = await differ.detect_changes()
    assert len(changes) == 0
