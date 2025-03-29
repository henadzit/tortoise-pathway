"""
Schema difference detection for Tortoise ORM migrations.

This module provides functionality to detect differences between Tortoise models
and the actual database schema, generating migration operations.
"""

import typing
from typing import Dict, List, Any, Optional
from enum import Enum

from tortoise import Tortoise
from tortoise.fields import Field
from tortoise.models import Model


class SchemaChangeType(Enum):
    """Types of schema changes that can be detected."""

    CREATE_TABLE = "create_table"
    DROP_TABLE = "drop_table"
    RENAME_TABLE = "rename_table"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN = "alter_column"
    RENAME_COLUMN = "rename_column"
    ADD_INDEX = "add_index"
    DROP_INDEX = "drop_index"
    ADD_CONSTRAINT = "add_constraint"
    DROP_CONSTRAINT = "drop_constraint"


class SchemaChange:
    """Represents a single schema change."""

    def __init__(
        self,
        change_type: SchemaChangeType,
        table_name: str,
        column_name: Optional[str] = None,
        new_name: Optional[str] = None,
        field_object: Optional[Field] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.change_type = change_type
        self.table_name = table_name

        # Ensure column_name is not None when a field_object is provided
        if column_name is None and field_object is not None:
            # Try to get the field name from source_field or from params
            source_field = getattr(field_object, "source_field", None)
            if source_field is not None:
                column_name = source_field
            elif params and "field_name" in params:
                column_name = params["field_name"]

        self.column_name = column_name
        self.new_name = new_name
        self.field_object = field_object
        self.params = params or {}

    def __str__(self) -> str:
        """String representation of the schema change."""
        if self.change_type == SchemaChangeType.CREATE_TABLE:
            return f"Create table {self.table_name}"
        elif self.change_type == SchemaChangeType.DROP_TABLE:
            return f"Drop table {self.table_name}"
        elif self.change_type == SchemaChangeType.RENAME_TABLE:
            return f"Rename table {self.table_name} to {self.new_name}"
        elif self.change_type == SchemaChangeType.ADD_COLUMN:
            return f"Add column {self.column_name} to table {self.table_name}"
        elif self.change_type == SchemaChangeType.DROP_COLUMN:
            return f"Drop column {self.column_name} from table {self.table_name}"
        elif self.change_type == SchemaChangeType.ALTER_COLUMN:
            return f"Alter column {self.column_name} on table {self.table_name}"
        elif self.change_type == SchemaChangeType.RENAME_COLUMN:
            return f"Rename column {self.column_name} to {self.new_name} on table {self.table_name}"
        elif self.change_type == SchemaChangeType.ADD_INDEX:
            return f"Add index on {self.column_name} in table {self.table_name}"
        elif self.change_type == SchemaChangeType.DROP_INDEX:
            return f"Drop index on {self.column_name} in table {self.table_name}"
        elif self.change_type == SchemaChangeType.ADD_CONSTRAINT:
            return f"Add constraint on {self.column_name} in table {self.table_name}"
        elif self.change_type == SchemaChangeType.DROP_CONSTRAINT:
            return f"Drop constraint on {self.column_name} in table {self.table_name}"
        return f"Unknown change {self.change_type} on {self.table_name}"

    def generate_sql_forward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for applying this change forward."""
        from tortoise_pathway.generators import generate_sql_for_schema_change

        return generate_sql_for_schema_change(self, "forward", dialect)

    def generate_sql_backward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting this change."""
        from tortoise_pathway.generators import generate_sql_for_schema_change

        return generate_sql_for_schema_change(self, "backward", dialect)


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
                notnull = column["notnull"]
                default_value = column["dflt_value"]
                is_pk = column["pk"] == 1

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
            changes.append(
                SchemaChange(
                    change_type=SchemaChangeType.CREATE_TABLE,
                    table_name=table_name,
                    params={"model": model_schema[table_name]["model"]},
                )
            )

        # Tables to drop (in DB but not in models)
        for table_name in db_tables - model_tables:
            changes.append(
                SchemaChange(change_type=SchemaChangeType.DROP_TABLE, table_name=table_name)
            )

        # Check changes in existing tables
        for table_name in db_tables & model_tables:
            # Columns in DB and model
            db_columns = set(db_schema[table_name]["columns"].keys())
            model_columns = set(model_schema[table_name]["columns"].keys())

            # Columns to add (in model but not in DB)
            for column_name in model_columns - db_columns:
                field_info = model_schema[table_name]["columns"][column_name]

                # Make sure column_name is correct (not None)
                if column_name is None and "field_name" in field_info:
                    actual_column_name = field_info["field_name"]
                else:
                    actual_column_name = column_name

                changes.append(
                    SchemaChange(
                        change_type=SchemaChangeType.ADD_COLUMN,
                        table_name=table_name,
                        column_name=actual_column_name,
                        field_object=field_info["field_object"],
                        params=field_info,
                    )
                )

            # Columns to drop (in DB but not in model)
            for column_name in db_columns - model_columns:
                changes.append(
                    SchemaChange(
                        change_type=SchemaChangeType.DROP_COLUMN,
                        table_name=table_name,
                        column_name=column_name,
                    )
                )

            # Check for column changes
            for column_name in db_columns & model_columns:
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
                        SchemaChange(
                            change_type=SchemaChangeType.ALTER_COLUMN,
                            table_name=table_name,
                            column_name=column_name,
                            field_object=model_column["field_object"],
                            params={"old": db_column, "new": model_column},
                        )
                    )

            # Index changes would be implemented similarly

        return changes
