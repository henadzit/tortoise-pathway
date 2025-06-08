"""
Tests for the SchemaDiffer's ability to detect field changes.
"""

from enum import IntEnum, Enum
from tortoise.fields import (
    IntField,
    CharField,
    DatetimeField,
    BooleanField,
    IntEnumField,
    CharEnumField,
)
from tortoise.fields.data import IntEnumFieldInstance, CharEnumFieldInstance
from tortoise.fields.relational import ManyToManyFieldInstance

from tortoise_pathway.state import State
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.operations import (
    AddField,
    AlterField,
    DropField,
    CreateModel,
)


async def test_detect_field_additions():
    """Test detecting added fields."""
    # Initialize state with a model without the field we'll add
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        table="test_model",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with an additional field
    def mock_get_model_schema():
        # Add a new field to the fields dictionary
        updated_fields = fields.copy()
        updated_fields["created_at"] = DatetimeField(auto_now_add=True)

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: AddField
    assert len(changes) == 1
    assert isinstance(changes[0], AddField)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"
    assert isinstance(changes[0].field_object, DatetimeField)
    assert changes[0].field_object.auto_now_add is True

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_field_removals():
    """Test detecting removed fields."""
    # Initialize state with a model with the field we'll remove
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

    # Mock the get_model_schema method to return a schema without the created_at field
    def mock_get_model_schema():
        # Create a copy without the created_at field
        updated_fields = {
            "id": IntField(primary_key=True),
            "name": CharField(max_length=100),
        }

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: DropField
    assert len(changes) == 1
    assert isinstance(changes[0], DropField)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_field_alterations():
    """Test detecting altered fields (changing field properties)."""
    # Initialize state with a model with the field we'll alter
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "is_active": BooleanField(default=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        table="test_model",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with altered field properties
    def mock_get_model_schema():
        # Create fields with altered properties
        updated_fields = {
            "id": IntField(primary_key=True),
            "name": CharField(max_length=200),  # Changed max_length
            "is_active": BooleanField(default=False),  # Changed default
        }

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be two changes: AlterField for name and is_active
    assert len(changes) == 2

    # Find the AlterField operations for each field
    name_changes = [c for c in changes if isinstance(c, AlterField) and c.field_name == "name"]
    active_changes = [
        c for c in changes if isinstance(c, AlterField) and c.field_name == "is_active"
    ]

    # Check for name field alteration
    assert len(name_changes) == 1
    name_change = name_changes[0]
    assert name_change.model == "test.TestModel"
    assert isinstance(name_change.field_object, CharField)
    assert name_change.field_object.max_length == 200

    # Check for is_active field alteration
    assert len(active_changes) == 1
    active_change = active_changes[0]
    assert active_change.model == "test.TestModel"
    assert isinstance(active_change.field_object, BooleanField)
    assert active_change.field_object.default is False

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_field_type_changes():
    """Test detecting altered fields (changing field type)."""
    # Initialize state with a model with the field we'll change type
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "count": IntField(default=0),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        table="test_model",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with changed field type
    def mock_get_model_schema():
        # Change count from IntField to BooleanField
        updated_fields = {
            "id": IntField(primary_key=True),
            "name": CharField(max_length=100),
            "count": BooleanField(default=False),  # Changed type
        }

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: AlterField for count
    assert len(changes) == 1
    assert isinstance(changes[0], AlterField)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "count"
    assert isinstance(changes[0].field_object, BooleanField)
    assert changes[0].field_object.default is False

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_multiple_field_changes():
    """Test detecting multiple field changes at once."""
    # Initialize state with a model
    state = State()

    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
        "count": IntField(default=0),
        "is_active": BooleanField(default=True),
    }

    create_model_op = CreateModel(
        model="test.TestModel",
        table="test_model",
        fields=fields,
    )

    state.apply_operation(create_model_op)

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with multiple changes
    def mock_get_model_schema():
        # Add a field, remove a field, and alter a field
        updated_fields = {
            "id": IntField(primary_key=True),
            "name": CharField(max_length=200),  # Altered max_length
            # count is removed
            "is_active": BooleanField(default=True),  # Unchanged
            "created_at": DatetimeField(auto_now_add=True),  # Added field
        }

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be three changes: AlterField, DropField, AddField
    assert len(changes) == 3

    # Check for the different types of changes
    add_changes = [c for c in changes if isinstance(c, AddField)]
    drop_changes = [c for c in changes if isinstance(c, DropField)]
    alter_changes = [c for c in changes if isinstance(c, AlterField)]

    # Check for added field
    assert len(add_changes) == 1
    add_field = add_changes[0]
    assert add_field.field_name == "created_at"

    # Check for dropped field
    assert len(drop_changes) == 1
    drop_field = drop_changes[0]
    assert drop_field.field_name == "count"

    # Check for altered field
    assert len(alter_changes) == 1
    alter_field = alter_changes[0]
    assert alter_field.field_name == "name"
    assert isinstance(alter_field.field_object, CharField)
    assert alter_field.field_object.max_length == 200

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_enum_field_additions():
    """Test detecting added enum fields."""

    # Define enums for our fields
    class Status(IntEnum):
        ACTIVE = 1
        INACTIVE = 0
        PENDING = 2

    class UserType(str, Enum):
        ADMIN = "admin"
        USER = "user"
        GUEST = "guest"

    # Initialize state with a model without the enum fields we'll add
    fields = {
        "id": IntField(primary_key=True),
        "name": CharField(max_length=100),
    }
    state = State(
        {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    }
                }
            }
        }
    )

    # Create a SchemaDiffer with our state
    differ = SchemaDiffer(state)

    # Mock the get_model_schema method to return a schema with additional enum fields
    def mock_get_model_schema():
        # Add new enum fields to the fields dictionary
        updated_fields = fields.copy()
        updated_fields["status"] = IntEnumField(Status, default=Status.INACTIVE)
        updated_fields["user_type"] = CharEnumField(UserType, default=UserType.USER)

        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": updated_fields,
                        "indexes": [],
                    }
                }
            }
        }

    # Replace the method with our mock
    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be two changes: AddField for each enum field
    assert len(changes) == 2

    # Find the changes for each field
    status_changes = [c for c in changes if isinstance(c, AddField) and c.field_name == "status"]
    user_type_changes = [
        c for c in changes if isinstance(c, AddField) and c.field_name == "user_type"
    ]

    # Check for status field addition
    assert len(status_changes) == 1
    status_change = status_changes[0]
    assert status_change.model == "test.TestModel"
    assert isinstance(status_change.field_object, IntEnumFieldInstance)
    assert status_change.field_object.default == Status.INACTIVE
    assert getattr(status_change.field_object, "enum_type", None) == Status

    # Check for user_type field addition
    assert len(user_type_changes) == 1
    user_type_change = user_type_changes[0]
    assert user_type_change.model == "test.TestModel"
    assert isinstance(user_type_change.field_object, CharEnumFieldInstance)
    assert user_type_change.field_object.default == UserType.USER
    assert getattr(user_type_change.field_object, "enum_type", None) == UserType

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_m2m_field_additions_to_existing_models():
    """Test detecting added m2m fields to two existing models."""
    # Initialize state with two models that don't have m2m relationship
    state = State(
        {
            "test": {
                "models": {
                    "User": {
                        "table": "user",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    },
                    "Project": {
                        "table": "project",
                        "fields": {
                            "id": IntField(primary_key=True),
                            "name": CharField(max_length=100),
                        },
                        "indexes": [],
                    },
                }
            }
        }
    )

    # Create a schema differ with our state
    differ = SchemaDiffer(state)

    # Define a schema with the same models but with m2m relationship added
    model_schema = {
        "test": {
            "models": {
                "User": {
                    "table": "user",
                    "fields": {
                        "id": IntField(primary_key=True),
                        "name": CharField(max_length=100),
                        "projects": ManyToManyFieldInstance(
                            "test.Project", related_name="users", through="user_project"
                        ),
                    },
                    "indexes": [],
                },
                "Project": {
                    "table": "project",
                    "fields": {
                        "id": IntField(primary_key=True),
                        "name": CharField(max_length=100),
                        "users": ManyToManyFieldInstance(
                            "test.User", related_name="projects", through="user_project"
                        ),
                    },
                    "indexes": [],
                },
            }
        }
    }

    # Replace the get_model_schema method to return our schema
    differ.get_model_schema = lambda: model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: AddField for the m2m relationship
    assert len(changes) == 1
    assert isinstance(changes[0], AddField)

    # Check the field was added correctly
    # It is impossible to tell the origin of the m2m field, so we check both
    change = changes[0]
    assert isinstance(change.field_object, ManyToManyFieldInstance)
    assert (change.model, change.field_name) in set(
        [("test.Project", "users"), ("test.User", "projects")]
    )
    assert (change.field_object.model_name, change.field_object.related_name) in set(
        [("test.User", "projects"), ("test.Project", "users")]
    )

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0


async def test_detect_field_index_addition():
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

    def mock_get_model_schema():
        return {
            "test": {
                "models": {
                    "TestModel": {
                        "table": "test_model",
                        "fields": {
                            **fields,
                            "created_at": DatetimeField(auto_now_add=True, db_index=True),
                        },
                    }
                }
            }
        }

    differ.get_model_schema = mock_get_model_schema

    # Detect changes
    changes = await differ.detect_changes()

    # There should be one change: AlterField for count
    assert len(changes) == 1
    assert isinstance(changes[0], AlterField)
    assert changes[0].model == "test.TestModel"
    assert changes[0].field_name == "created_at"
    assert isinstance(changes[0].field_object, DatetimeField)
    assert changes[0].field_object.index is True

    # check that the detected changes lead to a stable
    for change in changes:
        state.apply_operation(change)

    changes = await differ.detect_changes()
    assert len(changes) == 0
