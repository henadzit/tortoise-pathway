"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

from typing import Dict, Any, Optional, cast


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
        schemas: Dictionary mapping app names to their schema representations.
    """

    def __init__(self):
        """Initialize an empty state."""
        # New structure:
        # {
        #     'app_name': {
        #         'models': {
        #             'ModelName': {
        #                 'table': 'table_name',
        #                 'fields': {
        #                     'field_name': {
        #                         'column': 'column_name',
        #                         'type': 'field_type',
        #                         'nullable': True/False,
        #                         'default': default_value,
        #                         'primary_key': True/False,
        #                         'field_object': field_object,
        #                     }
        #                 },
        #                 'indexes': [
        #                     {'name': 'index_name', 'unique': True/False, 'columns': ['col1', 'col2']},
        #                 ],
        #             }
        #         }
        #     }
        # }
        self.schemas: Dict[str, Dict[str, Any]] = {}

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

        # Ensure the app exists in our state
        if app_name not in self.schemas:
            self.schemas[app_name] = {"models": {}}

        # Handle each type of operation
        if isinstance(operation, CreateModel):
            self._apply_create_model(app_name, model_name, operation)
        elif isinstance(operation, DropModel):
            self._apply_drop_model(app_name, model_name, operation)
        elif isinstance(operation, RenameModel):
            self._apply_rename_model(app_name, model_name, operation)
        elif isinstance(operation, AddField):
            self._apply_add_field(app_name, model_name, operation)
        elif isinstance(operation, DropField):
            self._apply_drop_field(app_name, model_name, operation)
        elif isinstance(operation, AlterField):
            self._apply_alter_field(app_name, model_name, operation)
        elif isinstance(operation, RenameField):
            self._apply_rename_field(app_name, model_name, operation)
        elif isinstance(operation, AddIndex):
            self._apply_add_index(app_name, model_name, operation)
        elif isinstance(operation, DropIndex):
            self._apply_drop_index(app_name, model_name, operation)
        elif isinstance(operation, AddConstraint):
            self._apply_add_constraint(app_name, model_name, operation)
        elif isinstance(operation, DropConstraint):
            self._apply_drop_constraint(app_name, model_name, operation)

    def _apply_create_model(self, app_name: str, model_name: str, operation: CreateModel) -> None:
        """Apply a CreateModel operation to the state."""
        table_name = operation.get_table_name(self)

        # Create a new model entry
        self.schemas[app_name]["models"][model_name] = {
            "table": table_name,
            "fields": {},
            "indexes": [],
        }

        # Add fields
        for field_name, field_obj in operation.fields.items():
            # Get the actual DB column name
            source_field = getattr(field_obj, "source_field", None)
            db_column = source_field if source_field is not None else field_name

            # Extract field properties
            nullable = getattr(field_obj, "null", False)
            default = getattr(field_obj, "default", None)
            pk = getattr(field_obj, "pk", False)
            field_type = field_obj.__class__.__name__

            # Add the field to the state
            self.schemas[app_name]["models"][model_name]["fields"][field_name] = {
                "column": db_column,
                "type": field_type,
                "nullable": nullable,
                "default": default,
                "primary_key": pk,
                "field_object": field_obj,
            }

    def _apply_drop_model(self, app_name: str, model_name: str, operation: DropModel) -> None:
        """Apply a DropModel operation to the state."""
        # Remove the model if it exists
        if model_name in self.schemas[app_name]["models"]:
            del self.schemas[app_name]["models"][model_name]

    def _apply_rename_model(self, app_name: str, model_name: str, operation: RenameModel) -> None:
        """Apply a RenameModel operation to the state."""
        new_table_name = operation.new_name

        if not new_table_name or model_name not in self.schemas[app_name]["models"]:
            return

        # Update the table name
        self.schemas[app_name]["models"][model_name]["table"] = new_table_name

    def _apply_add_field(self, app_name: str, model_name: str, operation: AddField) -> None:
        """Apply an AddField operation to the state."""
        column_name = operation.column_name
        field_obj = operation.field_object
        field_name = operation.field_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Extract field properties
        nullable = getattr(field_obj, "null", False)
        default = getattr(field_obj, "default", None)
        pk = getattr(field_obj, "pk", False)
        field_type = field_obj.__class__.__name__

        # Add the field to the state
        self.schemas[app_name]["models"][model_name]["fields"][field_name] = {
            "column": column_name,
            "type": field_type,
            "nullable": nullable,
            "default": default,
            "primary_key": pk,
            "field_object": field_obj,
        }

    def _apply_drop_field(self, app_name: str, model_name: str, operation: DropField) -> None:
        """Apply a DropField operation to the state."""
        field_name = operation.field_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Remove the field from the state
        if field_name in self.schemas[app_name]["models"][model_name]["fields"]:
            del self.schemas[app_name]["models"][model_name]["fields"][field_name]

    def _apply_alter_field(self, app_name: str, model_name: str, operation: AlterField) -> None:
        """Apply an AlterField operation to the state."""
        field_name = operation.field_name
        field_obj = operation.field_object

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Verify the field exists
        if field_name in self.schemas[app_name]["models"][model_name]["fields"]:
            # Extract field properties
            nullable = getattr(field_obj, "null", False)
            default = getattr(field_obj, "default", None)
            pk = getattr(field_obj, "pk", False)
            field_type = field_obj.__class__.__name__

            # Get the column name (keep the existing one)
            column_name = self.schemas[app_name]["models"][model_name]["fields"][field_name][
                "column"
            ]

            # Update the field in the state
            self.schemas[app_name]["models"][model_name]["fields"][field_name] = {
                "column": column_name,
                "type": field_type,
                "nullable": nullable,
                "default": default,
                "primary_key": pk,
                "field_object": field_obj,
            }

    def _apply_rename_field(self, app_name: str, model_name: str, operation: RenameField) -> None:
        """Apply a RenameField operation to the state."""
        old_field_name = operation.field_name
        new_field_name = operation.new_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Verify the old field exists
        if old_field_name in self.schemas[app_name]["models"][model_name]["fields"]:
            # Get the old field's data
            field_data = self.schemas[app_name]["models"][model_name]["fields"][old_field_name]

            # Add the field with the new name
            self.schemas[app_name]["models"][model_name]["fields"][new_field_name] = field_data

            # Remove the old field
            del self.schemas[app_name]["models"][model_name]["fields"][old_field_name]

    def _apply_add_index(self, app_name: str, model_name: str, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        if model_name not in self.schemas[app_name]["models"]:
            return

        # Get field names from operation
        fields = operation.fields if hasattr(operation, "fields") else [operation.field_name]

        # Convert field names to column names
        columns = []
        for field_name in fields:
            if field_name in self.schemas[app_name]["models"][model_name]["fields"]:
                column_name = self.schemas[app_name]["models"][model_name]["fields"][field_name][
                    "column"
                ]
                columns.append(column_name)

        # Add the index to the state
        if columns:
            self.schemas[app_name]["models"][model_name]["indexes"].append(
                {
                    "name": operation.index_name,
                    "unique": operation.unique,
                    "columns": columns,
                }
            )

    def _apply_drop_index(self, app_name: str, model_name: str, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        if model_name not in self.schemas[app_name]["models"]:
            return

        # Find and remove the index by name
        for i, index in enumerate(self.schemas[app_name]["models"][model_name]["indexes"]):
            if index["name"] == operation.index_name:
                del self.schemas[app_name]["models"][model_name]["indexes"][i]
                break

    def _apply_add_constraint(
        self, app_name: str, model_name: str, operation: AddConstraint
    ) -> None:
        """Apply an AddConstraint operation to the state."""
        # Constraints aren't directly represented in our schema state model yet
        # This is a simplified implementation
        pass

    def _apply_drop_constraint(
        self, app_name: str, model_name: str, operation: DropConstraint
    ) -> None:
        """Apply a DropConstraint operation to the state."""
        # Constraints aren't directly represented in our schema state model yet
        # This is a simplified implementation
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get the entire schema representation."""
        return self.schemas

    def get_models(self, app: str) -> Dict[str, Any]:
        """
        Get all models for a specific app.

        Args:
            app: The app name.

        Returns:
            Dictionary of models for the app.
        """
        if app in self.schemas and "models" in self.schemas[app]:
            return self.schemas[app]["models"]
        return {}

    def get_table_name(self, app: str, model: str) -> Optional[str]:
        """
        Get the table name for a specific model.

        Args:
            app: The app name.
            model: The model name.

        Returns:
            The table name, or None if not found.
        """
        try:
            return self.schemas[app]["models"][model]["table"]
        except (KeyError, TypeError):
            return None

    def get_column_name(self, app: str, model: str, field_name: str) -> Optional[str]:
        """
        Get the column name for a specific field.

        Args:
            app: The app name.
            model: The model name.
            field_name: The field name.

        Returns:
            The column name, or None if not found.
        """
        try:
            return self.schemas[app]["models"][model]["fields"][field_name]["column"]
        except (KeyError, TypeError):
            return field_name  # Fall back to using field name as column name
