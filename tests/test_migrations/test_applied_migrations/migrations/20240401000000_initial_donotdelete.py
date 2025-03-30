"""
Initial migration for test_applied_migrations app
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import CreateTable
from tortoise.fields.data import BooleanField
from tortoise.fields.data import CharField
from tortoise.fields.data import DatetimeField
from tortoise.fields.data import DecimalField
from tortoise.fields.data import IntField
from tortoise.fields.data import TextField


class InitialMigration(Migration):
    """
    Initial migration creating products and categories tables.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        # Create table products
        change_0 = CreateTable(
            table_name="products",
            fields={
                "id": IntField(pk=True),
                "name": CharField(max_length=255),
                "description": TextField(),
                "price": DecimalField(max_digits=10, decimal_places=2),
                "is_active": BooleanField(default=True),
                "created_at": DatetimeField(auto_now_add=True),
            },
        )
        await change_0.apply()

        # Create table categories
        change_1 = CreateTable(
            table_name="categories",
            fields={
                "id": IntField(pk=True),
                "name": CharField(max_length=100),
                "description": TextField(null=True),
            },
        )
        await change_1.apply()

    async def revert(self) -> None:
        """Revert the migration."""
        from tortoise_pathway.schema_change import DropTable

        # Drop table products
        change_0 = DropTable(
            table_name="products",
        )
        await change_0.apply()

        # Drop table categories
        change_1 = DropTable(
            table_name="categories",
        )
        await change_1.apply()
