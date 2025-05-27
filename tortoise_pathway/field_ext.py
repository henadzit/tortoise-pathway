"""
Utility functions for Tortoise Field objects.
"""

from tortoise.fields import Field, CharField, DatetimeField
from tortoise.fields.relational import RelationalField


def field_db_column(field: Field, field_name: str) -> str:
    """
    Get the database column name for a field. Usually you can get the column name from the Field object,
    however, it requires to initialize the Tortoise models which is not always possible in a migration.
    """
    source_field = getattr(field, "source_field", None)
    if source_field:
        return source_field
    elif isinstance(field, RelationalField):
        # Default to tortoise convention: field_name + "_id"
        return f"{field_name}_id"
    else:
        return field_name


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

    if hasattr(field, "unique") and field.unique and not field.pk:
        params.append("unique=True")

    if hasattr(field, "index") and field.index and not field.pk:
        params.append("db_index=True")

    if hasattr(field, "enum_type"):
        enum_type = getattr(field, "enum_type")
        params.append(f"enum_type={enum_type.__name__}")

    if hasattr(field, "default") and field.default is not None and not callable(field.default):
        if isinstance(field.default, str):
            params.append(f"default='{field.default}'")
        elif isinstance(field.default, bool):
            params.append(f"default={str(field.default)}")
        else:
            params.append(f"default={field.default}")

    if hasattr(field, "source_field") and field.source_field is not None:
        params.append(f"source_field='{field.source_field}'")

    # Handle field-specific attributes
    if isinstance(field, CharField) and hasattr(field, "max_length"):
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
        params.append(f"model_name='{related_model}'")

        if hasattr(field, "related_name"):
            related_name = getattr(field, "related_name")
            if related_name:
                params.append(f"related_name='{related_name}'")

        if hasattr(field, "on_delete"):
            on_delete = getattr(field, "on_delete")
            params.append(f"on_delete='{on_delete}'")

    if isinstance(field, DatetimeField):
        # Tortoise will set both auto_now and auto_now_add to True if auto_now_add is True,
        # even though you cannot pass both to the field constructor.
        # The following code ensures that both of them aren't True at the same time.
        if getattr(field, "auto_now", False):
            params.append("auto_now=True")
        elif getattr(field, "auto_now_add", False):
            params.append("auto_now_add=True")

    # Generate the final string representation
    return f"{field_type}({', '.join(params)})"
