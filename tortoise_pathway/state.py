"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

from typing import Dict, List, Any, Set, Optional, cast

from tortoise import Tortoise
from tortoise.models import Model

from tortoise_pathway.migration import Migration
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
        # Structure:
        # {
        #     'app_name': {
        #         'tables': {
        #             'table_name': {
        #                 'columns': {
        #                     'column_name': {
        #                         'type': 'field_type',
        #                         'nullable': True/False,
        #                         'default': default_value,
        #                         'primary_key': True/False,
        #                     }
        #                 },
        #                 'indexes': [
        #                     {'name': 'index_name', 'unique': True/False, 'columns': ['col1', 'col2']},
        #                 ],
        #                 'model': 'app_name.ModelName',
        #             }
        #         }
        #     }
        # }
        self.schemas: Dict[str, Dict[str, Any]] = {}

    async def build_from_migrations(self, migrations: List[Migration]) -> None:
        """
        Build the state based on a list of migrations.

        Args:
            migrations: List of Migration objects to apply to the state.
        """
        # Start with an empty state
        self.schemas = {}

        # Apply each migration's operations to the state
        for migration in migrations:
            for operation in migration.operations:
                self._apply_operation(operation)

    def _apply_operation(self, operation: SchemaChange) -> None:
        """
        Apply a single schema change operation to the state.

        Args:
            operation: The SchemaChange object to apply.
        """
        # Extract app_name from the model reference (format: "app_name.ModelName")
        app_name = operation.model.split(".")[0]

        # Ensure the app exists in our state
        if app_name not in self.schemas:
            self.schemas[app_name] = {"tables": {}}

        # Handle each type of operation
        if isinstance(operation, CreateTable):
            self._apply_create_table(app_name, operation)
        elif isinstance(operation, DropTable):
            self._apply_drop_table(app_name, operation)
        elif isinstance(operation, RenameTable):
            self._apply_rename_table(app_name, operation)
        elif isinstance(operation, AddColumn):
            self._apply_add_column(app_name, operation)
        elif isinstance(operation, DropColumn):
            self._apply_drop_column(app_name, operation)
        elif isinstance(operation, AlterColumn):
            self._apply_alter_column(app_name, operation)
        elif isinstance(operation, RenameColumn):
            self._apply_rename_column(app_name, operation)
        elif isinstance(operation, AddIndex):
            self._apply_add_index(app_name, operation)
        elif isinstance(operation, DropIndex):
            self._apply_drop_index(app_name, operation)
        elif isinstance(operation, AddConstraint):
            self._apply_add_constraint(app_name, operation)
        elif isinstance(operation, DropConstraint):
            self._apply_drop_constraint(app_name, operation)

    def _apply_create_table(self, app_name: str, operation: CreateTable) -> None:
        """Apply a CreateTable operation to the state."""
        table_name = operation.table_name

        # Create a new table entry
        self.schemas[app_name]["tables"][table_name] = {
            "columns": {},
            "indexes": [],
            "model": operation.model,
        }

        # Add columns from the fields
        for field_name, field_obj in operation.fields.items():
            # Get the actual DB column name
            source_field = getattr(field_obj, "source_field", None)
            db_column = source_field if source_field is not None else field_name

            # Extract field properties
            nullable = getattr(field_obj, "null", False)
            default = getattr(field_obj, "default", None)
            pk = getattr(field_obj, "pk", False)
            field_type = field_obj.__class__.__name__

            # Add the column to the state
            self.schemas[app_name]["tables"][table_name]["columns"][db_column] = {
                "field_name": field_name,
                "type": field_type,
                "nullable": nullable,
                "default": default,
                "primary_key": pk,
                "field_object": field_obj,
            }

    def _apply_drop_table(self, app_name: str, operation: DropTable) -> None:
        """Apply a DropTable operation to the state."""
        table_name = operation.table_name

        # Remove the table if it exists
        if table_name in self.schemas[app_name]["tables"]:
            del self.schemas[app_name]["tables"][table_name]

    def _apply_rename_table(self, app_name: str, operation: RenameTable) -> None:
        """Apply a RenameTable operation to the state."""
        table_name = operation.table_name
        new_name = operation.params.get("new_name")

        if not new_name or table_name not in self.schemas[app_name]["tables"]:
            return

        # Copy the table with the new name and delete the old one
        self.schemas[app_name]["tables"][new_name] = self.schemas[app_name]["tables"][
            table_name
        ].copy()
        del self.schemas[app_name]["tables"][table_name]

    def _apply_add_column(self, app_name: str, operation: AddColumn) -> None:
        """Apply an AddColumn operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name
        field_obj = operation.field_object

        if table_name not in self.schemas[app_name]["tables"]:
            return

        # Extract field properties
        field_name = operation.params.get("field_name", column_name)
        nullable = getattr(field_obj, "null", False)
        default = getattr(field_obj, "default", None)
        pk = getattr(field_obj, "pk", False)
        field_type = field_obj.__class__.__name__

        # Add the column to the state
        self.schemas[app_name]["tables"][table_name]["columns"][column_name] = {
            "field_name": field_name,
            "type": field_type,
            "nullable": nullable,
            "default": default,
            "primary_key": pk,
            "field_object": field_obj,
        }

    def _apply_drop_column(self, app_name: str, operation: DropColumn) -> None:
        """Apply a DropColumn operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name

        if (
            table_name in self.schemas[app_name]["tables"]
            and column_name in self.schemas[app_name]["tables"][table_name]["columns"]
        ):
            del self.schemas[app_name]["tables"][table_name]["columns"][column_name]

    def _apply_alter_column(self, app_name: str, operation: AlterColumn) -> None:
        """Apply an AlterColumn operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name
        field_obj = operation.field_object

        if (
            table_name not in self.schemas[app_name]["tables"]
            or column_name not in self.schemas[app_name]["tables"][table_name]["columns"]
        ):
            return

        # Extract field properties
        field_name = operation.params.get("field_name", column_name)
        nullable = getattr(field_obj, "null", False)
        default = getattr(field_obj, "default", None)
        pk = getattr(field_obj, "pk", False)
        field_type = field_obj.__class__.__name__

        # Update the column in the state
        self.schemas[app_name]["tables"][table_name]["columns"][column_name].update(
            {
                "field_name": field_name,
                "type": field_type,
                "nullable": nullable,
                "default": default,
                "primary_key": pk,
                "field_object": field_obj,
            }
        )

    def _apply_rename_column(self, app_name: str, operation: RenameColumn) -> None:
        """Apply a RenameColumn operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name
        new_name = operation.params.get("new_name")

        if (
            not new_name
            or table_name not in self.schemas[app_name]["tables"]
            or column_name not in self.schemas[app_name]["tables"][table_name]["columns"]
        ):
            return

        # Copy the column with the new name and delete the old one
        self.schemas[app_name]["tables"][table_name]["columns"][new_name] = self.schemas[app_name][
            "tables"
        ][table_name]["columns"][column_name].copy()
        del self.schemas[app_name]["tables"][table_name]["columns"][column_name]

    def _apply_add_index(self, app_name: str, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name

        if table_name not in self.schemas[app_name]["tables"]:
            return

        # Extract index information
        index_name = operation.params.get("name", f"idx_{column_name}")
        unique = operation.params.get("unique", False)
        columns = operation.params.get("columns", [column_name])

        # Add the index to the state
        self.schemas[app_name]["tables"][table_name]["indexes"].append(
            {
                "name": index_name,
                "unique": unique,
                "columns": columns,
            }
        )

    def _apply_drop_index(self, app_name: str, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        table_name = operation.table_name
        column_name = operation.column_name

        if table_name not in self.schemas[app_name]["tables"]:
            return

        # Get index name if provided
        index_name = operation.params.get("name")

        # Remove the index from the state
        if index_name:
            # Remove by name
            self.schemas[app_name]["tables"][table_name]["indexes"] = [
                idx
                for idx in self.schemas[app_name]["tables"][table_name]["indexes"]
                if idx["name"] != index_name
            ]
        else:
            # Remove by column
            self.schemas[app_name]["tables"][table_name]["indexes"] = [
                idx
                for idx in self.schemas[app_name]["tables"][table_name]["indexes"]
                if column_name not in idx["columns"]
            ]

    def _apply_add_constraint(self, app_name: str, operation: AddConstraint) -> None:
        """Apply an AddConstraint operation to the state."""
        # For simplicity, we're treating constraints as special indexes
        self._apply_add_index(app_name, cast(AddIndex, operation))

    def _apply_drop_constraint(self, app_name: str, operation: DropConstraint) -> None:
        """Apply a DropConstraint operation to the state."""
        # For simplicity, we're treating constraints as special indexes
        self._apply_drop_index(app_name, cast(DropIndex, operation))

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the combined schema representation for all apps.

        Returns:
            A dictionary representing the combined schema state.
        """
        # Flatten the schema structure to match the format used by SchemaDiffer
        combined_schema = {}

        for app_name, app_schema in self.schemas.items():
            for table_name, table_info in app_schema["tables"].items():
                combined_schema[table_name] = {
                    "columns": table_info["columns"],
                    "indexes": table_info["indexes"],
                    "model": table_info.get("model"),
                }

        return combined_schema
