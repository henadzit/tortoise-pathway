"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

from typing import Dict, Any, Optional, cast


from tortoise_pathway.schema_change import (
    SchemaChange,
    CreateTable,
    DropTable,
    RenameTable,
    AddColumn,
    DropColumn,
    AlterColumn,
    RenameColumn,
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
        if isinstance(operation, CreateTable):
            self._apply_create_table(app_name, model_name, operation)
        elif isinstance(operation, DropTable):
            self._apply_drop_table(app_name, model_name, operation)
        elif isinstance(operation, RenameTable):
            self._apply_rename_table(app_name, model_name, operation)
        elif isinstance(operation, AddColumn):
            self._apply_add_column(app_name, model_name, operation)
        elif isinstance(operation, DropColumn):
            self._apply_drop_column(app_name, model_name, operation)
        elif isinstance(operation, AlterColumn):
            self._apply_alter_column(app_name, model_name, operation)
        elif isinstance(operation, RenameColumn):
            self._apply_rename_column(app_name, model_name, operation)
        elif isinstance(operation, AddIndex):
            self._apply_add_index(app_name, model_name, operation)
        elif isinstance(operation, DropIndex):
            self._apply_drop_index(app_name, model_name, operation)
        elif isinstance(operation, AddConstraint):
            self._apply_add_constraint(app_name, model_name, operation)
        elif isinstance(operation, DropConstraint):
            self._apply_drop_constraint(app_name, model_name, operation)

    def _apply_create_table(self, app_name: str, model_name: str, operation: CreateTable) -> None:
        """Apply a CreateTable operation to the state."""
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

    def _apply_drop_table(self, app_name: str, model_name: str, operation: DropTable) -> None:
        """Apply a DropTable operation to the state."""
        # Remove the model if it exists
        if model_name in self.schemas[app_name]["models"]:
            del self.schemas[app_name]["models"][model_name]

    def _apply_rename_table(self, app_name: str, model_name: str, operation: RenameTable) -> None:
        """Apply a RenameTable operation to the state."""
        new_table_name = operation.new_name

        if not new_table_name or model_name not in self.schemas[app_name]["models"]:
            return

        # Update the table name
        self.schemas[app_name]["models"][model_name]["table"] = new_table_name

    def _apply_add_column(self, app_name: str, model_name: str, operation: AddColumn) -> None:
        """Apply an AddColumn operation to the state."""
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

    def _apply_drop_column(self, app_name: str, model_name: str, operation: DropColumn) -> None:
        """Apply a DropColumn operation to the state."""
        field_name = operation.field_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Remove the field from the state
        if field_name in self.schemas[app_name]["models"][model_name]["fields"]:
            del self.schemas[app_name]["models"][model_name]["fields"][field_name]

    def _apply_alter_column(self, app_name: str, model_name: str, operation: AlterColumn) -> None:
        """Apply an AlterColumn operation to the state."""
        column_name = operation.column_name
        field_obj = operation.field_object

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Find the field that maps to this column
        for field_name, field_info in self.schemas[app_name]["models"][model_name][
            "fields"
        ].items():
            if field_info.get("column") == column_name:
                # Extract field properties
                nullable = getattr(field_obj, "null", False)
                default = getattr(field_obj, "default", None)
                pk = getattr(field_obj, "pk", False)
                field_type = field_obj.__class__.__name__

                # Update the field in the state
                self.schemas[app_name]["models"][model_name]["fields"][field_name].update(
                    {
                        "type": field_type,
                        "nullable": nullable,
                        "default": default,
                        "primary_key": pk,
                        "field_object": field_obj,
                    }
                )
                break

    def _apply_rename_column(self, app_name: str, model_name: str, operation: RenameColumn) -> None:
        """Apply a RenameColumn operation to the state."""
        column_name = operation.column_name
        new_column_name = operation.new_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Find the field that maps to this column and update its column mapping
        for field_name, field_info in self.schemas[app_name]["models"][model_name][
            "fields"
        ].items():
            if field_info.get("column") == column_name:
                field_info["column"] = new_column_name
                break

    def _apply_add_index(self, app_name: str, model_name: str, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        if model_name not in self.schemas[app_name]["models"]:
            return

        # Extract index information from the operation
        index_name = operation.index_name
        unique = operation.unique
        columns = operation.columns

        # Add the index to the state
        self.schemas[app_name]["models"][model_name]["indexes"].append(
            {
                "name": index_name,
                "unique": unique,
                "columns": columns,
            }
        )

    def _apply_drop_index(self, app_name: str, model_name: str, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        field_name = operation.column_name  # Keep for compatibility, but should be renamed
        index_name = operation.index_name

        if model_name not in self.schemas[app_name]["models"]:
            return

        # Remove the index from the state
        if index_name:
            # Remove by name
            self.schemas[app_name]["models"][model_name]["indexes"] = [
                idx
                for idx in self.schemas[app_name]["models"][model_name]["indexes"]
                if idx["name"] != index_name
            ]
        else:
            # Remove by column - Get real column name if needed
            column_name = self.get_column_name(app_name, model_name, field_name)
            self.schemas[app_name]["models"][model_name]["indexes"] = [
                idx
                for idx in self.schemas[app_name]["models"][model_name]["indexes"]
                if column_name not in idx["columns"]
            ]

    def _apply_add_constraint(
        self, app_name: str, model_name: str, operation: AddConstraint
    ) -> None:
        """Apply an AddConstraint operation to the state."""
        # For simplicity, we're treating constraints as special indexes
        # Create a temporary AddIndex with the same properties
        from tortoise_pathway.schema_change import AddIndex

        temp_add_index = AddIndex(
            model=operation.model,
            column_name=operation.column_name,
            index_name=operation.constraint_name,
            unique=False,
            columns=[operation.column_name],
        )
        self._apply_add_index(app_name, model_name, temp_add_index)

    def _apply_drop_constraint(
        self, app_name: str, model_name: str, operation: DropConstraint
    ) -> None:
        """Apply a DropConstraint operation to the state."""
        # For simplicity, we're treating constraints as special indexes
        # Create a temporary DropIndex with the same properties
        from tortoise_pathway.schema_change import DropIndex

        temp_drop_index = DropIndex(
            model=operation.model,
            column_name=operation.column_name,
            index_name=operation.constraint_name,
        )
        self._apply_drop_index(app_name, model_name, temp_drop_index)

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the schema representation.

        Returns:
            The model-centric schema dictionary.
        """
        # Simply return the model-centric schema
        return self.schemas

    def get_models(self, app: str) -> Dict[str, Any]:
        """
        Get all models for a specific app.

        Args:
            app: Application name.

        Returns:
            Dictionary mapping model names to their definitions.
        """
        if app not in self.schemas:
            return {}

        return self.schemas[app].get("models", {})

    def get_table_name(self, app: str, model: str) -> Optional[str]:
        """
        Get the table name for a specific model.

        Args:
            app: Application name.
            model: Model name.

        Returns:
            The table name for the model, or a converted snake_case name if not found.
        """
        if app in self.schemas and model in self.schemas[app].get("models", {}):
            return self.schemas[app]["models"][model]["table"]

        return None

    def get_column_name(self, app: str, model: str, field_name: str) -> Optional[str]:
        """
        Get the column name for a specific field in a model.

        Args:
            app: Application name.
            model: Model name.
            field_name: Field name.

        Returns:
            The column name for the field, or the field name itself if not found.
        """
        if (
            app in self.schemas
            and model in self.schemas[app].get("models", {})
            and field_name in self.schemas[app]["models"][model].get("fields", {})
        ):
            return self.schemas[app]["models"][model]["fields"][field_name]["column"]

        return None
