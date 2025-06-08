"""
Tests for the SchemaDiffer's ability to detect model changes.
"""

from tortoise.fields import (
    IntField,
    CharField,
)
from tortoise.fields.relational import ForeignKeyFieldInstance

from tortoise_pathway.state import State
from tortoise_pathway.schema_differ import SchemaDiffer


async def test_detect_circular_reference_model_creation():
    """Test detecting model creation with circular references between models."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with circular references
    def mock_get_model_schema():
        return {
            "school": {
                "models": {
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "teacher": ForeignKeyFieldInstance(
                                "school.Teacher", related_name="courses", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                    "Teacher": {
                        "table": "teacher",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "user": ForeignKeyFieldInstance(
                                "user.User",
                                related_name="teachers",
                                to_field="id",
                            ),
                        },
                        "indexes": [],
                    },
                }
            },
            "user": {
                "models": {
                    "User": {
                        "table": "user",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    }
                }
            },
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 7 changes: CreateModel for all the models
    assert len(changes) == 3

    # Extract model names in order of creation
    model_names = [change.model.split(".")[-1] for change in changes]

    # Verify models with dependencies are created after the models they depend on
    # For example, Teacher depends on Department, so Department must come before Teacher
    def assert_model_created_before(dependent: str, dependency: str):
        assert model_names.index(dependent) > model_names.index(
            dependency
        ), f"{dependent} should be created after {dependency}"

    # User should be created before Teacher
    assert_model_created_before("Teacher", "User")

    # Teacher should be created before Course
    assert_model_created_before("Course", "Teacher")

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0
