"""
Schema difference detection for Tortoise ORM migrations.

This module provides the SchemaDiffer class that detects differences between
Tortoise models and the actual database schema.
"""

from typing import Dict, List, Any, Optional

from tortoise import Tortoise
from tortoise.models import Model

from tortoise_pathway.state import State
from tortoise_pathway.operations import (
    Operation,
    CreateModel,
    DropModel,
    AddField,
    DropField,
    AlterField,
    AddIndex,
    DropIndex,
)


class SchemaDiffer:
    """Detects differences between Tortoise models and database schema."""

    def __init__(self, app_name: str, state: Optional[State] = None, connection=None):
        """
        Initialize a schema differ for a specific app.

        Args:
            app_name: Name of the app to detect schema changes for
            state: Optional State object containing current state
            connection: Optional database connection
        """
        self.app_name = app_name
        self.connection = connection
        self.state = state or State(app_name)

    async def get_db_schema(self) -> Dict[str, Any]:
        """Get the current database schema for the app."""
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
        app_schema = self._convert_to_models_format(db_schema)
        return app_schema

    def _convert_to_models_format(self, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database schema to the models format for a single app."""
        app_schema = {"models": {}}

        for table_name, table_info in db_schema.items():
            # Extract model name from table name, assuming it follows conventions
            model_name = "".join(part.capitalize() for part in table_name.split("_"))

            # Create model entry
            app_schema["models"][model_name] = {
                "table": table_name,
                "fields": {},
                "indexes": table_info["indexes"],
            }

            # This conversion is incomplete as we don't have actual Field objects from the database
            # In a real implementation, we would need to create Field objects from the column info

        return app_schema

    def get_model_schema(self) -> Dict[str, Any]:
        """Get schema representation from Tortoise models for this app."""
        app_schema = {"models": {}}

        # Get models for this app only
        if self.app_name in Tortoise.apps:
            app_models = Tortoise.apps[self.app_name]

            for model_name, model in app_models.items():
                if not issubclass(model, Model):
                    continue

                # Get model's DB table name
                table_name = model._meta.db_table

                # Initialize model entry
                app_schema["models"][model_name] = {
                    "table": table_name,
                    "fields": {},
                    "indexes": [],
                }

                # Get fields
                for field_name, field_object in model._meta.fields_map.items():
                    # Skip reverse relations
                    if field_object.__class__.__name__ == "BackwardFKRelation":
                        continue

                    # Store the field object directly
                    app_schema["models"][model_name]["fields"][field_name] = field_object

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
                            app_schema["models"][model_name]["indexes"].append(
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
                            app_schema["models"][model_name]["indexes"].append(
                                {
                                    "name": f"uniq_{'_'.join(unique_columns)}",
                                    "unique": True,
                                    "columns": unique_columns,
                                }
                            )

        return app_schema

    async def detect_changes(self) -> List[Operation]:
        """
        Detect schema changes between models and state derived from migrations.

        Returns:
            List of Operation objects representing the detected changes.
        """
        current_schema = self.state.get_schema()
        model_schema = self.get_model_schema()
        changes = []

        # Create a map of table names to their model for easy lookup
        current_tables = {}
        model_tables = {}

        for model_name, model_info in current_schema["models"].items():
            current_tables[model_info["table"]] = model_name

        for model_name, model_info in model_schema["models"].items():
            model_tables[model_info["table"]] = model_name

        # Tables to create (in models but not in current schema)
        for table_name in sorted(set(model_tables.keys()) - set(current_tables.keys())):
            model_name = model_tables[table_name]
            # Get the model info and extract field objects
            model_info = model_schema["models"][model_name]
            field_objects = model_info["fields"]  # Field objects are already stored directly

            model_ref = f"{self.app_name}.{model_name}"
            operation = CreateModel(
                model=model_ref,
                fields=field_objects,
            )
            changes.append(operation)

        # Tables to drop (in current schema but not in models)
        for table_name in sorted(set(current_tables.keys()) - set(model_tables.keys())):
            model_name = current_tables[table_name]
            model_ref = f"{self.app_name}.{model_name}"
            changes.append(
                DropModel(
                    model=model_ref,
                )
            )

        # For tables that exist in both
        for table_name in sorted(set(current_tables.keys()) & set(model_tables.keys())):
            current_model_name = current_tables[table_name]
            model_model_name = model_tables[table_name]

            # Get the model info for both
            current_model = current_schema["models"][current_model_name]
            model_model = model_schema["models"][model_model_name]

            # Get field sets for comparison
            current_fields = current_model["fields"]
            model_fields = model_model["fields"]

            # Map of field names between current schema and model
            current_field_names = set(current_fields.keys())
            model_field_names = set(model_fields.keys())

            # Reference to the model
            model_ref = f"{self.app_name}.{model_model_name}"

            # Fields to add (in model but not in current schema)
            for field_name in sorted(model_field_names - current_field_names):
                field_obj = model_fields[field_name]
                changes.append(
                    AddField(
                        model=model_ref,
                        field_object=field_obj,
                        field_name=field_name,
                    )
                )

            # Fields to drop (in current schema but not in model)
            for field_name in sorted(current_field_names - model_field_names):
                changes.append(
                    DropField(
                        model=model_ref,
                        field_name=field_name,
                    )
                )

            # Fields to alter (in both, but might be different)
            for field_name in sorted(current_field_names & model_field_names):
                current_field = current_fields[field_name]
                model_field = model_fields[field_name]

                # Check if fields are different
                if self._are_fields_different(current_field, model_field):
                    changes.append(
                        AlterField(
                            model=model_ref,
                            field_object=model_field,
                            field_name=field_name,
                        )
                    )

            # Compare indexes
            # Get indexes from both current schema and model schema
            current_indexes = current_model.get("indexes", [])
            model_indexes = model_model.get("indexes", [])

            # Create maps of index names for easier comparison
            current_index_map = {idx["name"]: idx for idx in current_indexes}
            model_index_map = {idx["name"]: idx for idx in model_indexes}

            # Indexes to add (in model but not in current schema)
            for index_name in set(model_index_map.keys()) - set(current_index_map.keys()):
                index = model_index_map[index_name]
                # Use the first column as the primary field name for the AddIndex operation
                # The other columns will be included in the 'fields' parameter
                if index["columns"]:
                    primary_field_name = index["columns"][0]
                    # Find the corresponding field name from column name
                    for field_name, field_obj in model_fields.items():
                        source_field = getattr(field_obj, "source_field", None)
                        if source_field == primary_field_name or field_name == primary_field_name:
                            changes.append(
                                AddIndex(
                                    model=model_ref,
                                    field_name=field_name,
                                    index_name=index_name,
                                    unique=index["unique"],
                                    fields=index["columns"],
                                )
                            )
                            break

            # Indexes to drop (in current schema but not in model)
            for index_name in set(current_index_map.keys()) - set(model_index_map.keys()):
                index = current_index_map[index_name]
                # Use the first column as the primary field name for the DropIndex operation
                if index["columns"]:
                    primary_field_name = index["columns"][0]
                    # Find the corresponding field name from column name
                    for field_name, field_obj in current_fields.items():
                        source_field = getattr(field_obj, "source_field", None)
                        if source_field == primary_field_name or field_name == primary_field_name:
                            changes.append(
                                DropIndex(
                                    model=model_ref,
                                    field_name=field_name,
                                    index_name=index_name,
                                )
                            )
                            break

            # Indexes to alter (in both, but different)
            for index_name in set(current_index_map.keys()) & set(model_index_map.keys()):
                current_index = current_index_map[index_name]
                model_index = model_index_map[index_name]

                # Check if indexes are different
                if (
                    current_index["unique"] != model_index["unique"]
                    or current_index["columns"] != model_index["columns"]
                ):
                    # First drop the old index
                    if current_index["columns"]:
                        primary_field_name = current_index["columns"][0]
                        for field_name, field_obj in current_fields.items():
                            source_field = getattr(field_obj, "source_field", None)
                            if (
                                source_field == primary_field_name
                                or field_name == primary_field_name
                            ):
                                changes.append(
                                    DropIndex(
                                        model=model_ref,
                                        field_name=field_name,
                                        index_name=index_name,
                                    )
                                )
                                break

                    # Then add the new index
                    if model_index["columns"]:
                        primary_field_name = model_index["columns"][0]
                        for field_name, field_obj in model_fields.items():
                            source_field = getattr(field_obj, "source_field", None)
                            if (
                                source_field == primary_field_name
                                or field_name == primary_field_name
                            ):
                                changes.append(
                                    AddIndex(
                                        model=model_ref,
                                        field_name=field_name,
                                        index_name=index_name,
                                        unique=model_index["unique"],
                                        fields=model_index["columns"],
                                    )
                                )
                                break

        return changes

    def _are_fields_different(self, field1, field2) -> bool:
        """
        Compare two Field objects to determine if they are effectively different.

        Args:
            field1: First Field object
            field2: Second Field object

        Returns:
            True if the fields are different (require migration), False otherwise
        """
        # Check if they're the same class type
        if field1.__class__.__name__ != field2.__class__.__name__:
            return True

        # Check key field attributes that would require a migration
        important_attrs = [
            "null",
            "default",
            "pk",
            "unique",
            "index",
            "max_length",
            "description",
            "constraint_name",
            "reference",
            "auto_now",
            "auto_now_add",
        ]

        # For more strict comparison
        for attr in important_attrs:
            if (hasattr(field1, attr) and not hasattr(field2, attr)) or (
                not hasattr(field1, attr) and hasattr(field2, attr)
            ):
                return True

            if hasattr(field1, attr) and hasattr(field2, attr):
                val1 = getattr(field1, attr)
                val2 = getattr(field2, attr)
                if val1 != val2:
                    return True

        # For RelationalField objects, check additional attributes
        if hasattr(field1, "model_name") and hasattr(field2, "model_name"):
            if getattr(field1, "model_name") != getattr(field2, "model_name"):
                return True

            # Check related_name
            related_name1 = getattr(field1, "related_name", None)
            related_name2 = getattr(field2, "related_name", None)
            if related_name1 != related_name2:
                return True

        # Fields are effectively the same for migration purposes
        return False

    def _get_table_centric_schema(self, app_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert app-models schema to table-centric schema for comparison. DEPRECATED."""
        # This method is kept for backward compatibility but should not be used
        # in the new model-centric approach.
        return app_schema
