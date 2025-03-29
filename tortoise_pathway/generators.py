"""
Centralized code generators for Tortoise Pathway migrations.

This module contains all code generation functions for migrations to avoid duplication
across the codebase. It includes SQL generation and migration file templates.
"""

import datetime
from typing import List, Type, Union

from tortoise import Tortoise, Model

from tortoise_pathway.schema_diff import (
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


def generate_table_creation_sql(model: Type[Model], dialect: str = "sqlite") -> str:
    """
    Generate SQL for creating a table from a Tortoise model.

    Args:
        model: Tortoise model class.
        dialect: SQL dialect (default: "sqlite").

    Returns:
        SQL string for table creation.
    """
    table_name = model._meta.db_table
    columns = []
    constraints = []
    processed_column_names = set()  # Track column names to avoid duplicates

    # Process each field
    for field_name, field in model._meta.fields_map.items():
        # Skip reverse relations
        if field.__class__.__name__ == "BackwardFKRelation":
            continue

        field_type = field.__class__.__name__

        # Skip processing if this field maps to an already processed column
        # (like when a ForeignKeyField already added {field_name}_id)
        # ForeignKey fields in Tortoise ORM automatically create a column with "_id" suffix
        if field_type == "ForeignKeyField":
            # For ForeignKeyField, use the actual db column name (typically field_name + "_id")
            db_field_name = field.model_field_name
            source_field = getattr(field, "source_field", None)
            if source_field:
                db_column = source_field
            else:
                # Default to tortoise convention: field_name + "_id"
                db_column = f"{db_field_name}_id"
        else:
            # Get field properties for non-FK fields
            # Only use source_field if it's not None, otherwise fall back to field_name
            source_field = getattr(field, "source_field", None)
            db_column = source_field if source_field is not None else field_name

        # Skip if we've already processed this column name
        if db_column in processed_column_names:
            continue

        processed_column_names.add(db_column)

        nullable = getattr(field, "null", False)
        unique = getattr(field, "unique", False)
        pk = getattr(field, "pk", False)
        default = getattr(field, "default", None)

        # Determine SQL type from field type
        if field_type == "IntField":
            sql_type = "INTEGER"
        elif field_type == "CharField":
            max_length = getattr(field, "max_length", 255)
            sql_type = f"VARCHAR({max_length})"
        elif field_type == "TextField":
            sql_type = "TEXT"
        elif field_type == "BooleanField":
            sql_type = "BOOLEAN"
        elif field_type == "FloatField":
            sql_type = "REAL"
        elif field_type == "DecimalField":
            sql_type = "DECIMAL"
        elif field_type == "DatetimeField":
            sql_type = "TIMESTAMP"
        elif field_type == "DateField":
            sql_type = "DATE"
        elif field_type == "ForeignKeyField":
            # Using getattr to handle potential missing attributes safely
            related_model_name = getattr(field, "model_name", None)
            related_table = None

            if related_model_name and model._meta.app:
                app_models = Tortoise.apps.get(model._meta.app, {})
                if related_model_name in app_models:
                    related_table = app_models[related_model_name]

            if related_table:
                related_table_name = related_table._meta.db_table
                sql_type = "INTEGER"  # Assuming integer foreign keys

                # Add foreign key constraint
                constraints.append(
                    f"FOREIGN KEY ({db_column}) REFERENCES {related_table_name} (id)"
                )
            else:
                sql_type = "INTEGER"  # Fallback if related table not found
        else:
            sql_type = "TEXT"  # Default to TEXT for unknown types

        # Build column definition
        column_def = f"{db_column} {sql_type}"

        if pk:
            if dialect == "sqlite":
                column_def += " PRIMARY KEY"
                if field_type == "IntField":
                    column_def += " AUTOINCREMENT"
            else:
                column_def += " PRIMARY KEY"
                if field_type == "IntField" and dialect == "postgres":
                    # For PostgreSQL, we'd use SERIAL instead
                    sql_type = "SERIAL"
                    column_def = f"{db_column} {sql_type} PRIMARY KEY"

        if not nullable and not pk:
            column_def += " NOT NULL"

        if unique and not pk:
            column_def += " UNIQUE"

        if default is not None and not callable(default):
            if isinstance(default, bool):
                default_val = "1" if default else "0"
            elif isinstance(default, (int, float)):
                default_val = str(default)
            elif isinstance(default, str):
                default_val = f"'{default}'"
            else:
                default_val = f"'{default}'"

            column_def += f" DEFAULT {default_val}"

        columns.append(column_def)

    # Add index creation for any defined indexes
    indexes = []
    if hasattr(model._meta, "indexes"):
        meta_indexes = getattr(model._meta, "indexes", [])
        if isinstance(meta_indexes, (list, tuple)):
            for index_fields in meta_indexes:
                if not isinstance(index_fields, (list, tuple)):
                    continue

                # Create a list to hold valid column names
                safe_index_columns: List[str] = []

                for field_name in index_fields:
                    if field_name in model._meta.fields_map:
                        source_field = getattr(
                            model._meta.fields_map[field_name], "source_field", None
                        )
                        column_name = source_field if source_field is not None else field_name
                        safe_index_columns.append(str(column_name))

                if safe_index_columns:
                    indexes.append(
                        f"CREATE INDEX idx_{table_name}_{'_'.join(safe_index_columns)} ON {table_name} ({', '.join(safe_index_columns)});"
                    )

    # Add unique constraints
    if hasattr(model._meta, "unique_together"):
        meta_unique = getattr(model._meta, "unique_together", [])
        if isinstance(meta_unique, (list, tuple)):
            for unique_fields in meta_unique:
                if not isinstance(unique_fields, (list, tuple)):
                    continue

                # Create a list to hold valid column names
                safe_unique_columns: List[str] = []

                for field_name in unique_fields:
                    if field_name in model._meta.fields_map:
                        source_field = getattr(
                            model._meta.fields_map[field_name], "source_field", None
                        )
                        column_name = source_field if source_field is not None else field_name
                        safe_unique_columns.append(str(column_name))

                if safe_unique_columns:
                    constraints.append(f"UNIQUE ({', '.join(safe_unique_columns)})")

    # Build the CREATE TABLE statement
    sql = f"CREATE TABLE {table_name} (\n"
    sql += ",\n".join(["    " + col for col in columns])

    if constraints:
        sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

    sql += "\n);"

    if indexes:
        sql += "\n\n" + "\n".join(indexes)

    return sql


def generate_sql_for_schema_change(
    change: SchemaChange, direction: str = "forward", dialect: str = "sqlite"
) -> str:
    """
    Generate SQL for a schema change.

    Args:
        change: The schema change to generate SQL for.
        direction: Either "forward" or "backward".
        dialect: SQL dialect (default: "sqlite").

    Returns:
        SQL string for applying the change.
    """
    if direction == "forward":
        if isinstance(change, CreateTable):
            if change.model:
                return generate_table_creation_sql(change.model, dialect)
            return f"CREATE TABLE {change.table_name} (id INTEGER PRIMARY KEY);"

        elif isinstance(change, AddColumn):
            field_type = change.field_object.__class__.__name__
            nullable = getattr(change.field_object, "null", False)
            default = getattr(change.field_object, "default", None)

            sql = f"ALTER TABLE {change.table_name} ADD COLUMN {change.column_name}"

            # Map Tortoise field types to SQL types (simplified)
            if field_type == "CharField":
                max_length = getattr(change.field_object, "max_length", 255)
                sql += f" VARCHAR({max_length})"
            elif field_type == "IntField":
                sql += " INTEGER"
            elif field_type == "BooleanField":
                sql += " BOOLEAN"
            elif field_type == "DatetimeField":
                sql += " TIMESTAMP"
            else:
                sql += " TEXT"  # Default to TEXT for unknown types

            if not nullable:
                sql += " NOT NULL"

            if default is not None:
                if isinstance(default, str):
                    sql += f" DEFAULT '{default}'"
                else:
                    sql += f" DEFAULT {default}"

            return sql

        elif isinstance(change, DropTable):
            return f"DROP TABLE {change.table_name}"

        elif isinstance(change, RenameTable):
            if dialect == "sqlite":
                return f"ALTER TABLE {change.table_name} RENAME TO {change.new_name}"
            elif dialect == "postgres":
                return f"ALTER TABLE {change.table_name} RENAME TO {change.new_name}"
            else:
                return f"-- Rename table not implemented for dialect: {dialect}"

        elif isinstance(change, AlterColumn):
            if dialect == "sqlite":
                return f"-- SQLite doesn't support ALTER COLUMN directly. Create a new table with the new schema."
            elif dialect == "postgres":
                column_type = "TEXT"  # Default type
                field_type = change.field_object.__class__.__name__

                if field_type == "CharField":
                    max_length = getattr(change.field_object, "max_length", 255)
                    column_type = f"VARCHAR({max_length})"
                elif field_type == "IntField":
                    column_type = "INTEGER"
                elif field_type == "BooleanField":
                    column_type = "BOOLEAN"
                elif field_type == "DatetimeField":
                    column_type = "TIMESTAMP"

                return f"ALTER TABLE {change.table_name} ALTER COLUMN {change.column_name} TYPE {column_type}"
            else:
                return f"-- Alter column not implemented for dialect: {dialect}"

        elif isinstance(change, RenameColumn):
            if dialect == "sqlite":
                return f"-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the new schema."
            elif dialect == "postgres":
                return f"ALTER TABLE {change.table_name} RENAME COLUMN {change.column_name} TO {change.new_name}"
            else:
                return f"-- Rename column not implemented for dialect: {dialect}"

        elif isinstance(change, AddIndex):
            return f"CREATE INDEX idx_{change.table_name}_{change.column_name} ON {change.table_name} ({change.column_name})"

        elif isinstance(change, DropIndex):
            return f"DROP INDEX idx_{change.table_name}_{change.column_name}"

        elif isinstance(change, AddConstraint):
            return f"-- Add constraint operation not implemented yet"

        elif isinstance(change, DropConstraint):
            return f"-- Drop constraint operation not implemented yet"

    elif direction == "backward":
        if isinstance(change, CreateTable):
            return f"DROP TABLE {change.table_name}"

        elif isinstance(change, AddColumn):
            # SQLite has limited support for dropping columns
            if dialect == "sqlite":
                return f"-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
            else:
                return f"ALTER TABLE {change.table_name} DROP COLUMN {change.column_name}"

        elif isinstance(change, DropTable):
            if change.model:
                return generate_table_creation_sql(change.model, dialect)
            return f"-- Cannot automatically recreate table without model information"

        elif isinstance(change, RenameTable):
            if dialect == "sqlite":
                return f"ALTER TABLE {change.new_name} RENAME TO {change.table_name}"
            elif dialect == "postgres":
                return f"ALTER TABLE {change.new_name} RENAME TO {change.table_name}"
            else:
                return f"-- Rename table not implemented for dialect: {dialect}"

        elif isinstance(change, RenameColumn):
            if dialect == "sqlite":
                return f"-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the old schema."
            elif dialect == "postgres":
                return f"ALTER TABLE {change.table_name} RENAME COLUMN {change.new_name} TO {change.column_name}"
            else:
                return f"-- Rename column not implemented for dialect: {dialect}"

        elif isinstance(change, AddIndex):
            return f"DROP INDEX idx_{change.table_name}_{change.column_name}"

        elif isinstance(change, DropIndex):
            return f"CREATE INDEX idx_{change.table_name}_{change.column_name} ON {change.table_name} ({change.column_name})"

    return f"-- SQL generation not implemented for this change type"


def generate_migration_class_name(migration_name: str) -> str:
    """
    Generate a valid Python class name from a migration name.

    Args:
        migration_name: The migration name (usually with timestamp prefix).

    Returns:
        A valid Python class name.
    """
    # Strip timestamp if present (assuming format like YYYYMMDDHHMMSS_name)
    if "_" in migration_name and migration_name.split("_")[0].isdigit():
        class_base = migration_name.split("_", 1)[1]
    else:
        class_base = migration_name

    return f"{class_base.title().replace('_', '')}Migration"


def generate_timestamp() -> str:
    """Generate a timestamp string for migration names."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def generate_empty_migration(migration_name: str) -> str:
    """
    Generate empty migration file content.

    Args:
        migration_name: Name of the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    return f'''"""
Migration {migration_name}
"""

from tortoise_pathway.migration import Migration


class {class_name}(Migration):
    """
    Custom migration class.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        # Write your forward migration logic here
        pass

    async def revert(self) -> None:
        """Revert the migration."""
        # Write your backward migration logic here
        pass
'''


def generate_auto_migration(migration_name: str, changes: List[SchemaChange]) -> str:
    """
    Generate migration file content based on detected changes.

    Args:
        migration_name: Name of the migration.
        changes: List of schema changes to include in the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    # If no changes detected, return placeholder template
    if not changes:
        raise ValueError("No changes")

    # Prepare imports for schema change classes and models
    schema_changes_used = set()
    model_imports = set()

    for change in changes:
        # Add the change class name to imports
        schema_changes_used.add(change.__class__.__name__)

        # If we're generating a reverse operation as a different class type, add that too
        if isinstance(change, CreateTable):
            schema_changes_used.add("DropTable")

        # Add model imports if available
        if hasattr(change, "model") and change.model is not None:
            model_name = change.model.__name__
            model_module = change.model.__module__
            model_imports.add(f"from {model_module} import {model_name}")

    schema_imports = ", ".join(sorted(schema_changes_used))
    model_imports_str = "\n".join(sorted(model_imports))

    # Generate operations lists
    operations = []
    reverse_operations = []

    # Generate code for each change
    for i, change in enumerate(changes):
        change_var = f"change_{i}"

        # Add the forward operation code
        operations.append(change.to_migration(change_var))

        # Add the reverse operation code
        reverse_operations.append(change.to_migration_reverse(change_var))

    # Generate the final migration code
    indent = "        "
    operations_str = "\n".join(indent + line for line in "\n".join(operations).split("\n"))
    reverse_operations_str = "\n".join(
        indent + line for line in "\n".join(reverse_operations).split("\n")
    )

    return f'''"""
Auto-generated migration {migration_name}
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_diff import {schema_imports}
{model_imports_str}


class {class_name}(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
{operations_str}

    async def revert(self) -> None:
        """Revert the migration."""
{reverse_operations_str}
'''
