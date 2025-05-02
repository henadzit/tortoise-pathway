"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

import copy
from typing import Dict, List, Optional, Tuple, TypedDict, cast

from tortoise.fields import Field
from tortoise.fields.relational import ManyToManyFieldInstance
from tortoise.indexes import Index

from tortoise_pathway.operations import (
    Operation,
    CreateModel,
    DropModel,
    RenameModel,
    AddField,
    DropField,
    AlterField,
    RenameField,
    AddIndex,
    DropIndex,
    AddConstraint,
    DropConstraint,
)


class ModelSchema(TypedDict):
    table: str
    fields: Dict[str, Field]
    indexes: List[Index]


class Schema(TypedDict):
    models: Dict[str, ModelSchema]


class State:
    """
    Represents the state of the models based on applied migrations.

    This class is used to track the expected database schema state based on
    the migrations that have been applied, rather than querying the actual
    database schema directly.

    Attributes:
        app_name: Name of the app this state represents.
        schema: Dictionary mapping model names to their schema representations.
    """

    def __init__(self, app_name: str, schema: Optional[Schema] = None):
        """
        Initialize an empty state for a specific app.

        Args:
            app_name: Name of the app this state represents.
        """
        self.app_name = app_name
        # New structure:
        # {
        #     'models': {
        #         'ModelName': {
        #             'table': 'table_name',
        #             'fields': {
        #                 'field_name': field_object,  # The actual Field instance
        #             },
        #             'indexes': [
        #                 Index(
        #                     name='index_name',
        #                     fields=['col1', 'col2'],
        #                 ),
        #             ],
        #         }
        #     }
        # }
        self._schema: Schema = schema or {"models": {}}
        self._snapshots: List[Tuple[str, State]] = []

    def apply_operation(self, operation: Operation) -> None:
        """
        Apply a single schema change operation to the state.

        Args:
            operation: The Operation object to apply.
        """
        # Verify this operation is for the app this state represents
        if operation.app_name != self.app_name:
            raise ValueError(f"Operation for {operation.model} is not for app {self.app_name}")

        model_name = operation.model_name

        # Handle each type of operation
        if isinstance(operation, CreateModel):
            self._apply_create_model(model_name, operation)
        elif isinstance(operation, DropModel):
            self._apply_drop_model(model_name, operation)
        elif isinstance(operation, RenameModel):
            self._apply_rename_model(model_name, operation)
        elif isinstance(operation, AddField):
            self._apply_add_field(model_name, operation)
        elif isinstance(operation, DropField):
            self._apply_drop_field(model_name, operation)
        elif isinstance(operation, AlterField):
            self._apply_alter_field(model_name, operation)
        elif isinstance(operation, RenameField):
            self._apply_rename_field(model_name, operation)
        elif isinstance(operation, AddIndex):
            self._apply_add_index(model_name, operation)
        elif isinstance(operation, DropIndex):
            self._apply_drop_index(model_name, operation)
        elif isinstance(operation, AddConstraint):
            self._apply_add_constraint(model_name, operation)
        elif isinstance(operation, DropConstraint):
            self._apply_drop_constraint(model_name, operation)

    def snapshot(self, name: str) -> None:
        """
        Take a snapshot of the current state.

        Args:
            name: The name of the snapshot.
        """
        self._snapshots.append((name, copy.deepcopy(self)))

    def prev(self) -> "State":
        """
        Get the previous state.
        """
        if len(self._snapshots) == 1:
            return State(self.app_name)
        _, state = self._snapshots[-2]
        return state

    def _apply_create_model(self, model_name: str, operation: CreateModel) -> None:
        """Apply a CreateModel operation to the state."""
        # Create a new model entry
        self._schema["models"][model_name] = {
            "table": operation.table,
            "fields": operation.fields.copy(),
            "indexes": [],
        }

    def _apply_drop_model(self, model_name: str, operation: DropModel) -> None:
        """Apply a DropModel operation to the state."""
        # Remove the model if it exists
        if model_name in self._schema["models"]:
            del self._schema["models"][model_name]

    def _apply_rename_model(self, model_name: str, operation: RenameModel) -> None:
        """Apply a RenameModel operation to the state."""
        new_table_name = operation.new_name

        # Update the table name
        self._schema["models"][model_name]["table"] = new_table_name

    def _apply_add_field(self, model_name: str, operation: AddField) -> None:
        """Apply an AddField operation to the state."""
        field_obj = operation.field_object
        field_name = operation.field_name
        # Add the field directly to the state
        self._schema["models"][model_name]["fields"][field_name] = field_obj

        # m2m fields are bidirectional, so we need to add the field to the referred model
        if isinstance(field_obj, ManyToManyFieldInstance):
            m2m_field = cast(ManyToManyFieldInstance, field_obj)
            referred_model_name = m2m_field.model_name.split(".")[1]
            self._schema["models"][referred_model_name]["fields"][m2m_field.related_name] = (
                ManyToManyFieldInstance(
                    model_name=f"{self.app_name}.{model_name}",
                    through=m2m_field.through,
                    related_name=field_name,
                    on_delete=m2m_field.on_delete,
                )
            )

    def _apply_drop_field(self, model_name: str, operation: DropField) -> None:
        """Apply a DropField operation to the state."""
        field_name = operation.field_name

        # Remove the field from the state
        if field_name in self._schema["models"][model_name]["fields"]:
            del self._schema["models"][model_name]["fields"][field_name]

    def _apply_alter_field(self, model_name: str, operation: AlterField) -> None:
        """Apply an AlterField operation to the state."""
        field_name = operation.field_name
        field_obj = operation.field_object

        # Verify the field exists
        if field_name in self._schema["models"][model_name]["fields"]:
            # Replace with the new field object
            self._schema["models"][model_name]["fields"][field_name] = field_obj

    def _apply_rename_field(self, model_name: str, operation: RenameField) -> None:
        """Apply a RenameField operation to the state."""
        old_field_name = operation.field_name
        new_field_name = operation.new_name
        # Verify the old field exists
        if old_field_name in self._schema["models"][model_name]["fields"]:
            # Get the field object
            field_obj = self._schema["models"][model_name]["fields"][old_field_name]

            # Add the field with the new name
            self._schema["models"][model_name]["fields"][new_field_name] = field_obj

            # Remove the old field
            del self._schema["models"][model_name]["fields"][old_field_name]

    def _apply_add_index(self, model_name: str, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        self._schema["models"][model_name]["indexes"].append(operation.index)

    def _apply_drop_index(self, model_name: str, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        for i, index in enumerate(self._schema["models"][model_name]["indexes"]):
            if index.name == operation.index_name:
                del self._schema["models"][model_name]["indexes"][i]
                return

        raise ValueError(f"Index {operation.index_name} not found in {model_name}")

    def _apply_add_constraint(self, model_name: str, operation: AddConstraint) -> None:
        """Apply an AddConstraint operation to the state."""
        # Constraints aren't directly represented in our schema state model yet
        # This is a simplified implementation
        pass

    def _apply_drop_constraint(self, model_name: str, operation: DropConstraint) -> None:
        """Apply a DropConstraint operation to the state."""
        # Constraints aren't directly represented in our schema state model yet
        # This is a simplified implementation
        pass

    def get_schema(self) -> Schema:
        """Get the entire schema representation."""
        return {
            "models": {
                model_name: self.get_model(model_name)
                for model_name in self._schema["models"].keys()
            }
        }

    def get_model(self, model_name: str) -> ModelSchema:
        """
        Get a specific model for this app.

        Returns:
            Dictionary of the model.
        """
        return copy.copy(self._schema["models"][model_name])

    def get_table_name(self, model_name: str) -> Optional[str]:
        """
        Get the table name for a specific model.

        Args:
            model: The model name.

        Returns:
            The table name, or None if not found.
        """
        try:
            return self._schema["models"][model_name]["table"]
        except (KeyError, TypeError):
            return None

    def get_field(self, model: str, field_name: str) -> Optional[Field]:
        """
        Get the field object for a specific field.
        """
        if (
            model in self._schema["models"]
            and field_name in self._schema["models"][model]["fields"]
        ):
            return self._schema["models"][model]["fields"][field_name]
        return None

    def get_index(self, model_name: str, index_name: str) -> Optional[Index]:
        """
        Get the Index object by name.
        """
        if model_name not in self._schema["models"]:
            return None
        for index in self._schema["models"][model_name]["indexes"]:
            if index.name == index_name:
                return index
        return None

    def get_fields(self, model_name: str) -> Optional[Dict[str, Field]]:
        """
        Get all fields for a specific model.

        Args:
            model_name: The model name.

        Returns:
            Dictionary mapping field names to Field objects, or None if model not found.
        """
        if model_name in self._schema["models"]:
            return copy.copy(self._schema["models"][model_name]["fields"])
        return None

    def get_column_name(self, model_name: str, field_name: str) -> Optional[str]:
        """
        Get the column name for a specific field.

        Args:
            model_name: The model name.
            field_name: The field name.

        Returns:
            The column name, or None if not found.
        """
        try:
            if (
                model_name in self._schema["models"]
                and field_name in self._schema["models"][model_name]["fields"]
            ):
                field_obj = self._schema["models"][model_name]["fields"][field_name]
                # Get source_field if available, otherwise use field_name as the column name
                source_field = getattr(field_obj, "source_field", None)
                return source_field if source_field is not None else field_name
            return None
        except (KeyError, TypeError):
            return field_name  # Fall back to using field name as column name
