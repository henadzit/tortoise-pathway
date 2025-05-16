from tortoise_pathway.schema.base import BaseSchemaManager


class PostgresSchemaManager(BaseSchemaManager):
    def __init__(self):
        super().__init__("postgres")

    def _default_pk_type(self):
        return "SERIAL"


schema_manager = PostgresSchemaManager()
