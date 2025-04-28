from hashlib import sha256
from tortoise.indexes import Index


class UniqueIndex(Index):
    """
    A unique index.

    It should be moved to tortoise.indexes.UniqueIndex eventually.
    """

    def __init__(self, name: str, fields: tuple[str, ...] | list[str]):
        if name is None:
            raise ValueError("name is required for unique index")
        super().__init__(fields=fields, name=name)


def index_to_migration(index: Index) -> str:
    """
    Convert an Index object to its string representation for migrations.

    Args:
        index: The Index object to convert.

    Returns:
        A string representation of the Index that can be used in migrations.
    """
    index_type = index.__class__.__name__

    params = []
    if index.fields:
        fields = [f'"{field}"' for field in index.fields]
        params.append(f"fields=[{', '.join(fields)}]")
    if index.name:
        params.append(f"name='{index.name}'")

    return f"{index_type}({', '.join(params)})"


def gen_index_name(prefix: str, table_name: str, field_names: list[str] | tuple[str, ...]) -> str:
    table = table_name[:11]
    fields = "_".join(field_names)[:7]
    hashed = sha256(";".join([table, fields]).encode("utf-8")).hexdigest()[:6]
    return f"{prefix}_{table}_{fields}_{hashed}"
