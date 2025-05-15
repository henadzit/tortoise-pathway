from tortoise_pathway.schema.base import BaseSchemaManager


class PostgresSchemaManager(BaseSchemaManager):
    def __init__(self):
        super().__init__("postgres")


schema_manager = PostgresSchemaManager()
