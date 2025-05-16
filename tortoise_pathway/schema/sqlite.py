from tortoise.fields import Field, IntField

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

    def alter_column(
        self,
        table_name: str,
        column_name: str,
        prev_field: Field,
        new_field: Field,
    ) -> str:
        raise NotImplementedError("ALTER COLUMN is not supported in SQLite")

    def _default_pk_type(self):
        return "INTEGER"

    def _default_pk_keyword(self, pk_field: Field):
        return "PRIMARY KEY" + (" AUTOINCREMENT" if isinstance(pk_field, IntField) else "")


schema_manager = SqliteSchemaManager()
