"""
Tests for the SchemaDiffer's ability to detect model changes.
"""

import pytest
from graphlib import CycleError
from typing import Dict, Any, cast
from tortoise.fields import (
    IntField,
    CharField,
    DatetimeField,
)
from tortoise.fields.relational import ForeignKeyFieldInstance, ManyToManyFieldInstance

from tortoise_pathway.state import State
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.operations import CreateModel, AddField


async def test_detect_basic_model_creation():
    """Test detecting a single model creation with no relations."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with a new model
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "created_at": DatetimeField(auto_now_add=True),
                        },
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: CreateModel
    assert len(changes) == 1
    assert isinstance(changes[0], CreateModel)
    assert changes[0].model == "test.TestModel"

    # Access fields on the CreateModel operation
    create_model_op = cast(CreateModel, changes[0])
    assert len(create_model_op.fields) == 3
    assert isinstance(create_model_op.fields["id"], IntField)
    assert isinstance(create_model_op.fields["name"], CharField)
    assert isinstance(create_model_op.fields["created_at"], DatetimeField)

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_single_relation_model_creation():
    """Test detecting model creation with a single foreign key relation."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with related models
    def mock_get_model_schema():
        # Define the parent model fields
        user_fields: Dict[str, Any] = {
            "id": IntField(primary_key=True),
            "name": CharField(max_length=100),
        }

        # Define the child model fields with a foreign key
        post_fields: Dict[str, Any] = {
            "id": IntField(primary_key=True),
            "title": CharField(max_length=100),
            "content": CharField(max_length=1000),
            "user": ForeignKeyFieldInstance(
                "test.User", related_name="posts", to_field="id"
            ),
        }

        return {
            "test": {
                "models": {
                    "User": {
                        "table": "user",
                        "fields": user_fields,
                        "indexes": [],
                    },
                    "Post": {
                        "table": "post",
                        "fields": post_fields,
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be two changes: CreateModel for User and Post
    assert len(changes) == 2

    # First change should be creating the User model (referenced model should be created first)
    assert isinstance(changes[0], CreateModel)
    assert changes[0].model == "test.User"

    user_model = cast(CreateModel, changes[0])
    assert len(user_model.fields) == 2  # id, name

    # Second change should be creating the Post model
    assert isinstance(changes[1], CreateModel)
    assert changes[1].model == "test.Post"

    post_model = cast(CreateModel, changes[1])
    assert len(post_model.fields) == 4  # id, title, content, and user FK
    assert isinstance(post_model.fields["user"], ForeignKeyFieldInstance)

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_multiple_relations_model_creation():
    """Test detecting model creation with multiple foreign key relations between models."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with multiple related models
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "Post": {
                        "table": "post",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "title": CharField(max_length=100),
                            "content": CharField(max_length=1000),
                            "user": ForeignKeyFieldInstance(
                                "test.User", related_name="posts", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                    "User": {
                        "table": "user",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    },
                    "Comment": {
                        "table": "comment",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "text": CharField(max_length=500),
                            "user": ForeignKeyFieldInstance(
                                "test.User", related_name="comments", to_field="id"
                            ),
                            "post": ForeignKeyFieldInstance(
                                "test.Post", related_name="comments", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be three changes: CreateModel for User, Post, and Comment
    assert len(changes) == 3

    # Changes should come in the correct order to respect dependencies
    # First User, then Post, then Comment
    model_names = [change.model.split(".")[-1] for change in changes]
    assert model_names == ["User", "Post", "Comment"]

    # Check that the Comment model has both ForeignKey fields
    comment_model = cast(
        CreateModel, [m for m in changes if m.model == "test.Comment"][0]
    )
    assert isinstance(comment_model.fields["user"], ForeignKeyFieldInstance)
    assert isinstance(comment_model.fields["post"], ForeignKeyFieldInstance)

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_circular_reference_model_creation():
    """Test detecting model creation with circular references between models."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with circular references
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "teacher": ForeignKeyFieldInstance(
                                "test.Teacher", related_name="courses", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                    "Teacher": {
                        "table": "teacher",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "department": ForeignKeyFieldInstance(
                                "test.Department",
                                related_name="teachers",
                                to_field="id",
                            ),
                        },
                        "indexes": [],
                    },
                    "Department": {
                        "table": "department",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "school": ForeignKeyFieldInstance(
                                "test.School", related_name="departments", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                    "School": {
                        "table": "school",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "admin": ForeignKeyFieldInstance(
                                "test.Admin", related_name="schools", to_field="id"
                            ),
                        },
                        "indexes": [],
                    },
                    "Admin": {
                        "table": "admin",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    },
                    "Student": {
                        "table": "student",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    },
                    "StudentCourse": {
                        "table": "student_course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "student": ForeignKeyFieldInstance(
                                "test.Student", related_name="courses", to_field="id"
                            ),
                            "course": ForeignKeyFieldInstance(
                                "test.Course", related_name="students", to_field="id"
                            ),
                            "grade": CharField(max_length=2, null=True),
                        },
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 7 changes: CreateModel for all the models
    assert len(changes) == 7

    # Extract model names in order of creation
    model_names = [change.model.split(".")[-1] for change in changes]

    # Verify models with dependencies are created after the models they depend on
    # For example, Teacher depends on Department, so Department must come before Teacher
    def assert_model_created_before(dependent: str, dependency: str):
        assert model_names.index(dependent) > model_names.index(
            dependency
        ), f"{dependent} should be created after {dependency}"

    # Admin should be created before School
    assert_model_created_before("School", "Admin")

    # School should be created before Department
    assert_model_created_before("Department", "School")

    # Department should be created before Teacher
    assert_model_created_before("Teacher", "Department")

    # Teacher should be created before Course
    assert_model_created_before("Course", "Teacher")

    # Student should be created before StudentCourse
    assert_model_created_before("StudentCourse", "Student")

    # Course should be created before StudentCourse
    assert_model_created_before("StudentCourse", "Course")

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_both_m2m_models_created():
    """Test detecting M2M relationship when both models are being created."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with M2M relationship
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "Student": {
                        "table": "student",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "courses": ManyToManyFieldInstance(
                                "test.Course",
                                related_name="students",
                                through="student_course",
                            ),
                        },
                        "indexes": [],
                    },
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "students": ManyToManyFieldInstance(
                                "test.Student",
                                related_name="courses",
                                through="student_course",
                            ),
                        },
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 3 changes: CreateModel for Student, CreateModel for Course,
    # and one AddField for the M2M relation
    assert len(changes) == 3

    assert isinstance(changes[0], CreateModel)
    assert changes[0].model == "test.Course"
    assert isinstance(changes[1], CreateModel)
    assert changes[1].model == "test.Student"
    assert isinstance(changes[2], AddField)
    assert changes[2].field_name == "students"
    assert isinstance(changes[2].field_object, ManyToManyFieldInstance)
    assert changes[2].field_object.model_name == "test.Student"
    assert changes[2].field_object.through == "student_course"

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_one_m2m_model_exists():
    """Test detecting M2M relationship when one model exists and another is being added."""
    # Initialize state with one of the M2M models already existing
    state = State(
        {
            "test": {
                "models": {
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    }
                }
            }
        },
    )

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with both models including M2M relationship
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "Student": {
                        "table": "student",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "courses": ManyToManyFieldInstance(
                                "test.Course",
                                related_name="students",
                                through="student_course",
                            ),
                        },
                        "indexes": [],
                    },
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                            "students": ManyToManyFieldInstance(
                                "test.Student",
                                related_name="courses",
                                through="student_course",
                            ),
                        },
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 2 changes: CreateModel for Student and one AddField for m2m relation
    assert len(changes) == 2

    assert isinstance(changes[0], CreateModel)
    assert changes[0].model == "test.Student"
    assert isinstance(changes[1], AddField)
    assert changes[1].field_name == "courses"
    assert isinstance(changes[1].field_object, ManyToManyFieldInstance)
    assert changes[1].field_object.model_name == "test.Course"
    assert changes[1].field_object.through == "student_course"

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_verify_cross_app_creation_dependencies():
    """Test detecting model creation order with cross-app dependencies."""
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


async def test_detect_field_dependencies_on_fk_add_for_new_model():
    """Test detecting M2M relationship when one model exists and another is being added."""
    # Initialize state with one of the M2M models already existing
    state = State(
        {
            "school": {
                "models": {
                    "Course": {
                        "table": "course",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    }
                }
            }
        },
    )

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with both models including M2M relationship
    updated_schema = {
        "school": {
            "models": {
                "Course": {
                    "table": "course",
                    "fields": {
                        "id": IntField(primary_key=True),
                        "name": CharField(max_length=100),
                        "teacher": ForeignKeyFieldInstance(
                            "user.User", related_name="teacher", to_field="id"
                        ),
                    },
                    "indexes": [],
                }
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
    differ.get_model_schema = lambda: updated_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 2 changes: CreateModel for Student and one AddField for m2m relation
    assert len(changes) == 2

    assert isinstance(changes[0], CreateModel)
    assert changes[0].model == "user.User"
    assert isinstance(changes[1], AddField)
    assert changes[1].field_name == "teacher"
    assert changes[1].model == "school.Course"
    assert isinstance(changes[1].field_object, ForeignKeyFieldInstance)
    assert changes[1].field_object.model_name == "user.User"
    assert changes[1].field_object.to_field == "id"

    # Check that school depends on user for the fk field pointing to the new user model
    app_dependencies = await differ.get_change_app_dependencies()
    assert app_dependencies == {"school": ["user"]}

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0

    # Add new fk field on existing table
    updated_schema["school"]["models"]["Course"]["fields"]["janitor"] = (
        ForeignKeyFieldInstance("user.User", related_name="janitor", to_field="id")
    )

    # Detect changes
    changes = await differ.detect_changes()

    # There should be 1 change: AddField for the new fk field
    assert len(changes) == 1

    assert isinstance(changes[0], AddField)
    assert changes[0].field_name == "janitor"
    assert changes[0].model == "school.Course"
    assert isinstance(changes[0].field_object, ForeignKeyFieldInstance)
    assert changes[0].field_object.model_name == "user.User"
    assert changes[0].field_object.to_field == "id"

    # Check that school depends on user for the fk field pointing to the new user model
    app_dependencies = await differ.get_change_app_dependencies()
    assert app_dependencies == {}


async def test_detect_cycle_error_on_creation():
    """Test that a CycleError is raised when models have a circular dependency."""
    # Initialize state with no models
    state = State()

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with two models that depend on each other
    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "ModelA": {
                        "table": "model_a",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "model_b": ForeignKeyFieldInstance(
                                "test.ModelB", related_name="a_s"
                            ),
                        },
                        "indexes": [],
                    },
                    "ModelB": {
                        "table": "model_b",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "model_a": ForeignKeyFieldInstance(
                                "test.ModelA", related_name="b_s"
                            ),
                        },
                        "indexes": [],
                    },
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes, expecting a CycleError
    with pytest.raises(CycleError) as excinfo:
        await differ.detect_changes()

    # Check that the error message contains the model names
    assert "test.ModelA" in str(excinfo.value)
    assert "test.ModelB" in str(excinfo.value)
