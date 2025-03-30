"""
Initial migration for test_model_changes app
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import CreateTable
from tortoise.fields.data import CharField
from tortoise.fields.data import DatetimeField
from tortoise.fields.data import IntField
from tortoise.fields.data import TextField


class InitialMigration(Migration):
    """
    Initial migration creating blogs and tags tables.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        # Create table blogs
        change_0 = CreateTable(
            table_name="blogs",
            fields={
                "id": IntField(pk=True),
                "title": CharField(max_length=255),
                "content": TextField(),
                "created_at": DatetimeField(auto_now_add=True),
                # Note: summary and updated_at fields are missing in the initial migration
            },
        )
        await change_0.apply()

        # Create table tags
        change_1 = CreateTable(
            table_name="tags",
            fields={
                "id": IntField(pk=True),
                "name": CharField(max_length=50, unique=True),
                # Note: description field is missing in the initial migration
            },
        )
        await change_1.apply()

        # Note: Comment model is missing in the initial migration

    async def revert(self) -> None:
        """Revert the migration."""
        from tortoise_pathway.schema_change import DropTable

        # Drop table blogs
        change_0 = DropTable(
            table_name="blogs",
        )
        await change_0.apply()

        # Drop table tags
        change_1 = DropTable(
            table_name="tags",
        )
        await change_1.apply()
