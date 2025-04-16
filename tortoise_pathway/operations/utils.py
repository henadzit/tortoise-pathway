"""
Utility functions for operations.
"""

from typing import Any
from tortoise.converters import encoders
from tortoise.fields import Field
from tortoise.fields.relational import RelationalField


def field_to_migration(field: Field) -> str:
    """
    Convert a Field object to its string representation for migrations.

    Args:
        field: The Field object to convert.

    Returns:
        A string representation of the Field that can be used in migrations.
    """
    field_type = field.__class__.__name__
    field_module = field.__class__.__module__

    # Start with importing the field if needed
    if "tortoise.fields" not in field_module:
        # For custom fields, include the full module path
        field_type = f"{field_module}.{field_type}"

    # Collect parameters
    params = []

    # Handle common field attributes
    if hasattr(field, "pk") and field.pk:
        params.append("primary_key=True")

    if hasattr(field, "null") and field.null:
        params.append("null=True")

    if hasattr(field, "unique") and field.unique:
        params.append("unique=True")

    if hasattr(field, "default") and field.default is not None and not callable(field.default):
        if isinstance(field.default, str):
            params.append(f"default='{field.default}'")
        elif isinstance(field.default, bool):
            params.append(f"default={str(field.default)}")
        else:
            params.append(f"default={field.default}")

    # Handle field-specific attributes
    if field_type == "CharField" and hasattr(field, "max_length"):
        # The hasattr check ensures the attribute exists before accessing
        max_length = getattr(field, "max_length")
        params.append(f"max_length={max_length}")

    if field_type == "DecimalField":
        if hasattr(field, "max_digits"):
            max_digits = getattr(field, "max_digits")
            params.append(f"max_digits={max_digits}")
        if hasattr(field, "decimal_places"):
            decimal_places = getattr(field, "decimal_places")
            params.append(f"decimal_places={decimal_places}")

    if isinstance(field, RelationalField):
        related_model = getattr(field, "model_name")
        params.append(f"'{related_model}'")

        if hasattr(field, "related_name"):
            related_name = getattr(field, "related_name")
            if related_name:
                params.append(f"related_name='{related_name}'")

        if hasattr(field, "on_delete"):
            on_delete = getattr(field, "on_delete")
            params.append(f"on_delete='{on_delete}'")

        params.append(f"source_field='{field.source_field}'")

    # Generate the final string representation
    return f"{field_type}({', '.join(params)})"


def default_to_sql(default: Any, dialect: str) -> Any:
    """
    Convert a default value to its SQL representation.
    """
    if dialect == "postgres" and isinstance(default, bool):
        return default

    return encoders.get(type(default))(default)
