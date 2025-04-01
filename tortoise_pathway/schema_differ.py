"""
Schema difference detection for Tortoise ORM migrations.

This module provides the SchemaDiffer class that detects differences between
Tortoise models and the actual database schema.
"""

from typing import Dict, List, Any, Optional

from tortoise import Tortoise
from tortoise.models import Model

from tortoise_pathway.state import State
from tortoise_pathway.schema_change import (
    SchemaChange,
    CreateTable,
    DropTable,
    AddColumn,
    DropColumn,
    AlterColumn,
)


class SchemaDiffer:
    """Detects differences between Tortoise models and database schema."""

    def __init__(self, state: Optional[State] = None, connection=None):
        self.connection = connection
        self.state = state or State()

    async def get_db_schema(self) -> Dict[str, Any]:
        """Get the current database schema."""
        conn = self.connection or Tortoise.get_connection("default")
        db_schema = {}

        # This is a simplified version. A real implementation would:
        # - Get all tables
        # - Get columns for each table
        # - Get indexes and constraints

        # Example for SQLite (would need different implementations for other DBs)
        tables = await conn.execute_query("SELECT name FROM sqlite_master WHERE type='table'")

        for table_record in tables[1]:
            table_name = table_record["name"]

            # Skip the migration tracking table and SQLite system tables
            if table_name == "tortoise_migrations" or table_name.startswith("sqlite_"):
                continue

            # Get column information
            columns_info = await conn.execute_query(f"PRAGMA table_info({table_name})")

            columns = {}
            for column in columns_info[1]:
                column_name = column["name"]
                column_type = column["type"]
                default_value = column["dflt_value"]
                is_pk = column["pk"] == 1
                notnull = column["notnull"] or is_pk

                columns[column_name] = {
                    "type": column_type,
                    "nullable": not notnull,
                    "default": default_value,
                    "primary_key": is_pk,
                }

            # Get index information
            indexes_info = await conn.execute_query(f"PRAGMA index_list({table_name})")

            indexes = []
            for index in indexes_info[1]:
                index_name = index["name"]
                is_unique = index["unique"]

                # Get columns in this index
                index_columns_info = await conn.execute_query(f"PRAGMA index_info({index_name})")
                index_columns = [col["name"] for col in index_columns_info[1]]

                indexes.append({"name": index_name, "unique": is_unique, "columns": index_columns})

            db_schema[table_name] = {"columns": columns, "indexes": indexes}

        # Convert to the new structure format
        app_schema = self._convert_to_app_models_format(db_schema)
        return app_schema

    def _convert_to_app_models_format(self, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database schema to the app-models format."""
        app_schema = {}

        # For DB schema without model information, use 'unknown' app as default
        if "unknown" not in app_schema:
            app_schema["unknown"] = {"models": {}}

        for table_name, table_info in db_schema.items():
            # Extract model name from table name, assuming it follows conventions
            model_name = "".join(part.capitalize() for part in table_name.split("_"))

            # If we can infer app name from table_info["model"], use it
            app_name = "unknown"
            if "model" in table_info and "." in table_info["model"]:
                app_name = table_info["model"].split(".")[0]
                model_name = table_info["model"].split(".")[1]

            # Ensure app exists in the schema
            if app_name not in app_schema:
                app_schema[app_name] = {"models": {}}

            # Create model entry
            app_schema[app_name]["models"][model_name] = {
                "table": table_name,
                "fields": {},
                "indexes": table_info["indexes"],
            }

            # Convert columns to fields
            for column_name, column_info in table_info["columns"].items():
                # Use column name as field name if no field_name is provided
                field_name = column_info.get("field_name", column_name)

                app_schema[app_name]["models"][model_name]["fields"][field_name] = {
                    "column": column_name,
                    "type": column_info["type"],
                    "nullable": column_info["nullable"],
                    "default": column_info["default"],
                    "primary_key": column_info["primary_key"],
                    "field_object": column_info.get("field_object"),
                }

        return app_schema

    def get_model_schema(self) -> Dict[str, Any]:
        """Get schema representation from Tortoise models."""
        app_schema = {}

        # For each registered model
        for app_name, app_models in Tortoise.apps.items():
            if app_name not in app_schema:
                app_schema[app_name] = {"models": {}}

            for model_name, model in app_models.items():
                if not issubclass(model, Model):
                    continue

                # Get model's DB table name
                table_name = model._meta.db_table

                # Initialize model entry
                app_schema[app_name]["models"][model_name] = {
                    "table": table_name,
                    "fields": {},
                    "indexes": [],
                }

                # Get fields
                for field_name, field_object in model._meta.fields_map.items():
                    # Skip reverse relations
                    if field_object.__class__.__name__ == "BackwardFKRelation":
                        continue

                    # Get field properties
                    field_type = field_object.__class__.__name__
                    nullable = getattr(field_object, "null", False)
                    default = getattr(field_object, "default", None)
                    pk = getattr(field_object, "pk", False)

                    # Get the actual DB column name
                    source_field = getattr(field_object, "source_field", None)
                    db_column = source_field if source_field is not None else field_name

                    app_schema[app_name]["models"][model_name]["fields"][field_name] = {
                        "column": db_column,
                        "type": field_type,
                        "nullable": nullable,
                        "default": default,
                        "primary_key": pk,
                        "field_object": field_object,
                    }

                # Get indexes
                if hasattr(model._meta, "indexes") and isinstance(
                    model._meta.indexes, (list, tuple)
                ):
                    for index_fields in model._meta.indexes:
                        if not isinstance(index_fields, (list, tuple)):
                            continue

                        index_columns = []
                        for field_name in index_fields:
                            if field_name in model._meta.fields_map:
                                source_field = getattr(
                                    model._meta.fields_map[field_name], "source_field", None
                                )
                                column_name = (
                                    source_field if source_field is not None else field_name
                                )
                                index_columns.append(column_name)

                        if index_columns:
                            app_schema[app_name]["models"][model_name]["indexes"].append(
                                {
                                    "name": f"idx_{'_'.join(index_columns)}",
                                    "unique": False,
                                    "columns": index_columns,
                                }
                            )

                # Get unique constraints
                if hasattr(model._meta, "unique_together") and isinstance(
                    model._meta.unique_together, (list, tuple)
                ):
                    for unique_fields in model._meta.unique_together:
                        if not isinstance(unique_fields, (list, tuple)):
                            continue

                        unique_columns = []
                        for field_name in unique_fields:
                            if field_name in model._meta.fields_map:
                                source_field = getattr(
                                    model._meta.fields_map[field_name], "source_field", None
                                )
                                column_name = (
                                    source_field if source_field is not None else field_name
                                )
                                unique_columns.append(column_name)

                        if unique_columns:
                            app_schema[app_name]["models"][model_name]["indexes"].append(
                                {
                                    "name": f"uniq_{'_'.join(unique_columns)}",
                                    "unique": True,
                                    "columns": unique_columns,
                                }
                            )

        return app_schema

    async def detect_changes(self) -> List[SchemaChange]:
        """
        Detect schema changes between models and state derived from migrations.

        Returns:
            List of SchemaChange objects representing the detected changes.
        """
        current_schema = self.state.get_schema()
        model_schema = self.get_model_schema()
        changes = []

        # Create a map of table names to their app/model for easy lookup
        current_tables = {}
        model_tables = {}

        for app_name, app_info in current_schema.items():
            for model_name, model_info in app_info.get("models", {}).items():
                current_tables[model_info["table"]] = (app_name, model_name)

        for app_name, app_info in model_schema.items():
            for model_name, model_info in app_info.get("models", {}).items():
                model_tables[model_info["table"]] = (app_name, model_name)

        # Tables to create (in models but not in current schema)
        for table_name in sorted(set(model_tables.keys()) - set(current_tables.keys())):
            app_name, model_name = model_tables[table_name]
            # Get the model info and extract field objects
            model_info = model_schema[app_name]["models"][model_name]
            field_objects = {}

            for field_name, field_info in model_info["fields"].items():
                field_obj = field_info.get("field_object")
                if field_obj is not None:
                    field_objects[field_name] = field_obj

            model_ref = f"{app_name}.{model_name}"
            operation = CreateTable(
                model=model_ref,
                fields=field_objects,
            )
            changes.append(operation)

        # Tables to drop (in current schema but not in models)
        for table_name in sorted(set(current_tables.keys()) - set(model_tables.keys())):
            app_name, model_name = current_tables[table_name]
            model_ref = f"{app_name}.{model_name}"
            changes.append(
                DropTable(
                    model=model_ref,
                )
            )

        # Check changes in existing tables (both in model and current schema)
        for table_name in sorted(set(current_tables.keys()) & set(model_tables.keys())):
            current_app_name, current_model_name = current_tables[table_name]
            model_app_name, model_model_name = model_tables[table_name]

            current_model = current_schema[current_app_name]["models"][current_model_name]
            model_model = model_schema[model_app_name]["models"][model_model_name]

            model_ref = f"{model_app_name}.{model_model_name}"

            # Map of column names to field names for both schemas
            current_columns = {
                field_info["column"]: field_name
                for field_name, field_info in current_model["fields"].items()
            }
            model_columns = {
                field_info["column"]: field_name
                for field_name, field_info in model_model["fields"].items()
            }

            # Columns to add (in model but not in current schema)
            for column_name in sorted(set(model_columns.keys()) - set(current_columns.keys())):
                field_name = model_columns[column_name]
                field_info = model_model["fields"][field_name]
                field_obj = field_info.get("field_object")

                if field_obj is not None:
                    changes.append(
                        AddColumn(
                            model=model_ref,
                            field_object=field_obj,
                            field_name=field_name,
                        )
                    )

            # Columns to drop (in current schema but not in model)
            for column_name in sorted(set(current_columns.keys()) - set(model_columns.keys())):
                changes.append(
                    DropColumn(
                        model=model_ref,
                        column_name=column_name,
                    )
                )

            # Columns to alter (in both, but different)
            for column_name in sorted(set(current_columns.keys()) & set(model_columns.keys())):
                current_field_name = current_columns[column_name]
                model_field_name = model_columns[column_name]

                current_field = current_model["fields"][current_field_name]
                model_field = model_model["fields"][model_field_name]

                # Check if there are differences that require altering
                if (
                    current_field["type"] != model_field["type"]
                    or current_field["nullable"] != model_field["nullable"]
                ):
                    field_obj = model_field.get("field_object")
                    if field_obj is not None:
                        changes.append(
                            AlterColumn(
                                model=model_ref,
                                column_name=column_name,
                                field_object=field_obj,
                                field_name=model_field_name,
                            )
                        )

        return changes

    def _get_table_centric_schema(self, app_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert app-models schema to table-centric schema for comparison. DEPRECATED."""
        # This method is kept for backward compatibility but should not be used
        # in the new model-centric approach.
        return app_schema
