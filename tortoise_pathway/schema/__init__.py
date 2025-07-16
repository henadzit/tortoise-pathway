import importlib

from tortoise import BaseDBAsyncClient

from tortoise_pathway.schema.base import BaseSchemaManager


def get_schema_manager(connection: BaseDBAsyncClient) -> BaseSchemaManager:
    dialect = connection.capabilities.dialect
    module = importlib.import_module(f"tortoise_pathway.schema.{dialect}")
    return module.schema_manager
