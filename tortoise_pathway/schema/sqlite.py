
from tortoise_pathway.schema.base import BaseSchemaManager


class SqliteSchemaManager(BaseSchemaManager):
    def __init__(self):
        super().__init__("sqlite")

    def add_foreign_key_column(
        self, table_name: str, column_name: str, related_table: str, to_column: str, null: bool
    ) -> str:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} INT"

        if not null:
            sql += " NOT NULL"

        sql += f" REFERENCES {related_table}({to_column})"
        return sql


schema_manager = SqliteSchemaManager()
