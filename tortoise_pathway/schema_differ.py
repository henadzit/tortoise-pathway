"""
Schema difference detection for Tortoise ORM migrations.

This module provides the SchemaDiffer class that detects differences between
Tortoise models and the actual database schema.
"""

from typing import Dict, List, Any

from tortoise import Tortoise
from tortoise.models import Model

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

    def __init__(self, connection=None):
        self.connection = connection

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

        return db_schema

    def get_model_schema(self) -> Dict[str, Any]:
        """Get schema representation from Tortoise models."""
        model_schema = {}

        # For each registered model
        for app_name, app_models in Tortoise.apps.items():
            for model_name, model in app_models.items():
                if not issubclass(model, Model):
                    continue

                # Get model's DB table name
                table_name = model._meta.db_table

                # Get fields
                columns = {}
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

                    columns[db_column] = {
                        "field_name": field_name,
                        "type": field_type,
                        "nullable": nullable,
                        "default": default,
                        "primary_key": pk,
                        "field_object": field_object,
                    }

                # Get indexes
                indexes = []
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
                            indexes.append(
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
                            indexes.append(
                                {
                                    "name": f"uniq_{'_'.join(unique_columns)}",
                                    "unique": True,
                                    "columns": unique_columns,
                                }
                            )

                model_schema[table_name] = {"columns": columns, "indexes": indexes, "model": model}

        return model_schema

    async def detect_changes(self) -> List[SchemaChange]:
        """Detect schema changes between models and database."""
        db_schema = await self.get_db_schema()
        model_schema = self.get_model_schema()

        changes = []

        # Detect table changes
        db_tables = set(db_schema.keys())
        model_tables = set(model_schema.keys())

        # Tables to create (in models but not in DB)
        for table_name in model_tables - db_tables:
            # Extract all field objects from the model for CreateTable
            field_objects = {}
            for column_name, column_info in model_schema[table_name]["columns"].items():
                if "field_object" in column_info:
                    field_name = column_info["field_name"]
                    field_objects[field_name] = column_info["field_object"]

            changes.append(
                CreateTable(
                    table_name=table_name,
                    fields=field_objects,
                    model=model_schema[table_name]["model"]._meta.full_name,
                    params={},
                )
            )

        # Tables to drop (in DB but not in models)
        for table_name in sorted(db_tables - model_tables):
            # For tables that don't exist in models, we need to pass a default model reference
            # Since model is now required, we'll use a placeholder value
            changes.append(
                DropTable(
                    table_name=table_name,
                    model=f"unknown.{table_name}",  # Use a placeholder for tables that don't exist in models
                )
            )

        # Check changes in existing tables
        for table_name in sorted(db_tables & model_tables):
            # Store model reference
            model = model_schema[table_name]["model"]

            # Columns in DB and model
            db_columns = set(db_schema[table_name]["columns"].keys())
            model_columns = set(model_schema[table_name]["columns"].keys())

            # Columns to add (in model but not in DB)
            for column_name in sorted(model_columns - db_columns):
                field_info = model_schema[table_name]["columns"][column_name]

                changes.append(
                    AddColumn(
                        table_name=table_name,
                        column_name=column_name,
                        field_object=field_info["field_object"],
                        model=model._meta.full_name,
                        params=field_info,
                    )
                )

            # Columns to drop (in DB but not in model)
            for column_name in db_columns - model_columns:
                changes.append(
                    DropColumn(
                        table_name=table_name,
                        column_name=column_name,
                        model=model._meta.full_name,
                    )
                )

            # Check for column changes
            for column_name in sorted(db_columns & model_columns):
                db_column = db_schema[table_name]["columns"][column_name]
                model_column = model_schema[table_name]["columns"][column_name]

                # This is simplified - a real implementation would compare types more carefully
                # Checking nullable changes, type changes, default value changes
                column_changed = False

                # For simplicity: if any property is different, mark as changed
                if db_column["nullable"] != model_column["nullable"]:
                    column_changed = True

                # Comparing types is tricky as DB types may not exactly match Python types
                # This would need more sophisticated comparison

                if column_changed:
                    changes.append(
                        AlterColumn(
                            table_name=table_name,
                            column_name=column_name,
                            field_object=model_column["field_object"],
                            model=model._meta.full_name,
                            params={"old": db_column, "new": model_column},
                        )
                    )

            # Index changes would be implemented similarly

        return changes
