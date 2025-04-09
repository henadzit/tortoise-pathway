"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

import copy
from typing import Dict, Any, List, Optional, Tuple, cast

from tortoise.fields import Field

from tortoise_pathway.schema_change import (
    SchemaChange,
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

    def __init__(self, app_name: str):
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
        #                 {'name': 'index_name', 'unique': True/False, 'columns': ['col1', 'col2']},
        #             ],
        #         }
        #     }
        # }
        self.schema: Dict[str, Dict[str, Any]] = {"models": {}}
        self.snapshots: List[Tuple[str, State]] = []

    def apply_operation(self, operation: SchemaChange) -> None:
        """
        Apply a single schema change operation to the state.

        Args:
            operation: The SchemaChange object to apply.
        """
        # Extract app_name and model_name from the model reference (format: "app_name.ModelName")
        parts = operation.model.split(".")
        app_name = parts[0]
        model_name = parts[1] if len(parts) > 1 else ""

        # Verify this operation is for the app this state represents
        if app_name != self.app_name:
            return

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
        self.snapshots.append((name, copy.deepcopy(self)))

    def prev(self) -> "State":
        """
        Get the previous state.
        """
        if len(self.snapshots) == 1:
            return State(self.app_name)
        _, state = self.snapshots[-2]
        return state

    def _apply_create_model(self, model_name: str, operation: CreateModel) -> None:
        """Apply a CreateModel operation to the state."""
        table_name = operation.get_table_name(self)

        # Create a new model entry
        self.schema["models"][model_name] = {
            "table": table_name,
            "fields": {},
            "indexes": [],
        }

        # Add fields directly from the operation
        for field_name, field_obj in operation.fields.items():
            self.schema["models"][model_name]["fields"][field_name] = field_obj

    def _apply_drop_model(self, model_name: str, operation: DropModel) -> None:
        """Apply a DropModel operation to the state."""
        # Remove the model if it exists
        if model_name in self.schema["models"]:
            del self.schema["models"][model_name]

    def _apply_rename_model(self, model_name: str, operation: RenameModel) -> None:
        """Apply a RenameModel operation to the state."""
        new_table_name = operation.new_name

        if not new_table_name or model_name not in self.schema["models"]:
            return

        # Update the table name
        self.schema["models"][model_name]["table"] = new_table_name

    def _apply_add_field(self, model_name: str, operation: AddField) -> None:
        """Apply an AddField operation to the state."""
        field_obj = operation.field_object
        field_name = operation.field_name

        if model_name not in self.schema["models"]:
            return

        # Add the field directly to the state
        self.schema["models"][model_name]["fields"][field_name] = field_obj

    def _apply_drop_field(self, model_name: str, operation: DropField) -> None:
        """Apply a DropField operation to the state."""
        field_name = operation.field_name

        if model_name not in self.schema["models"]:
            return

        # Remove the field from the state
        if field_name in self.schema["models"][model_name]["fields"]:
            del self.schema["models"][model_name]["fields"][field_name]

    def _apply_alter_field(self, model_name: str, operation: AlterField) -> None:
        """Apply an AlterField operation to the state."""
        field_name = operation.field_name
        field_obj = operation.field_object

        if model_name not in self.schema["models"]:
            return

        # Verify the field exists
        if field_name in self.schema["models"][model_name]["fields"]:
            # Replace with the new field object
            self.schema["models"][model_name]["fields"][field_name] = field_obj

    def _apply_rename_field(self, model_name: str, operation: RenameField) -> None:
        """Apply a RenameField operation to the state."""
        old_field_name = operation.field_name
        new_field_name = operation.new_name

        if model_name not in self.schema["models"]:
            return

        # Verify the old field exists
        if old_field_name in self.schema["models"][model_name]["fields"]:
            # Get the field object
            field_obj = self.schema["models"][model_name]["fields"][old_field_name]

            # Add the field with the new name
            self.schema["models"][model_name]["fields"][new_field_name] = field_obj

            # Remove the old field
            del self.schema["models"][model_name]["fields"][old_field_name]

    def _apply_add_index(self, model_name: str, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        if model_name not in self.schema["models"]:
            return

        # Get field names from operation
        fields = operation.fields if hasattr(operation, "fields") else [operation.field_name]

        # Get column names from the fields
        columns = []
        for field_name in fields:
            if field_name in self.schema["models"][model_name]["fields"]:
                field_obj = self.schema["models"][model_name]["fields"][field_name]
                # Get the column name from the field object or use field name as default
                column_name = getattr(field_obj, "source_field", field_name)
                columns.append(column_name)

        # Add the index to the state
        if columns:
            self.schema["models"][model_name]["indexes"].append(
                {
                    "name": operation.index_name,
                    "unique": operation.unique,
                    "columns": columns,
                }
            )

    def _apply_drop_index(self, model_name: str, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        if model_name not in self.schema["models"]:
            return

        # Find and remove the index by name
        for i, index in enumerate(self.schema["models"][model_name]["indexes"]):
            if index["name"] == operation.index_name:
                del self.schema["models"][model_name]["indexes"][i]
                break

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

    def get_schema(self) -> Dict[str, Any]:
        """Get the entire schema representation."""
        return self.schema

    def get_models(self) -> Dict[str, Any]:
        """
        Get all models for this app.

        Returns:
            Dictionary of models for the app.
        """
        return self.schema["models"]

    def get_table_name(self, model: str) -> Optional[str]:
        """
        Get the table name for a specific model.

        Args:
            model: The model name.

        Returns:
            The table name, or None if not found.
        """
        try:
            return self.schema["models"][model]["table"]
        except (KeyError, TypeError):
            return None

    def get_field(self, model: str, field_name: str) -> Optional[Field]:
        """
        Get the field object for a specific field.
        """
        if model in self.schema["models"] and field_name in self.schema["models"][model]["fields"]:
            return self.schema["models"][model]["fields"][field_name]
        return None

    def get_fields(self, model: str) -> Optional[Dict[str, Field]]:
        """
        Get all fields for a specific model.

        Args:
            model: The model name.

        Returns:
            Dictionary mapping field names to Field objects, or None if model not found.
        """
        if model in self.schema["models"]:
            return self.schema["models"][model]["fields"]
        return None

    def get_column_name(self, model: str, field_name: str) -> Optional[str]:
        """
        Get the column name for a specific field.

        Args:
            model: The model name.
            field_name: The field name.

        Returns:
            The column name, or None if not found.
        """
        try:
            if (
                model in self.schema["models"]
                and field_name in self.schema["models"][model]["fields"]
            ):
                field_obj = self.schema["models"][model]["fields"][field_name]
                # Get source_field if available, otherwise use field_name as the column name
                source_field = getattr(field_obj, "source_field", None)
                return source_field if source_field is not None else field_name
            return None
        except (KeyError, TypeError):
            return field_name  # Fall back to using field name as column name
