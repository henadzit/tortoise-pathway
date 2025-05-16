import importlib

from tortoise_pathway.schema.base import BaseSchemaManager


def get_schema_manager(dialect: str) -> BaseSchemaManager:
    module = importlib.import_module(f"tortoise_pathway.schema.{dialect}")
    return module.schema_manager
