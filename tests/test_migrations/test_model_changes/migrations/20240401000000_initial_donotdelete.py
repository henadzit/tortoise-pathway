"""
Initial migration for test_model_changes app
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import CreateTable, DropTable
from tortoise.fields.data import CharField
from tortoise.fields.data import DatetimeField
from tortoise.fields.data import IntField
from tortoise.fields.data import TextField


class InitialMigration(Migration):
    """
    Initial migration creating blogs and tags tables.
    """

    dependencies = []
    operations = [
        CreateTable(
            table_name="blogs",
            fields={
                "id": IntField(primary_key=True),
                "title": CharField(max_length=255),
                "content": TextField(),
                "created_at": DatetimeField(auto_now_add=True),
                # Note: summary and updated_at fields are missing in the initial migration
            },
        ),
        CreateTable(
            table_name="tags",
            fields={
                "id": IntField(primary_key=True),
                "name": CharField(max_length=50, unique=True),
                # Note: description field is missing in the initial migration
            },
        ),
        # Note: Comment model is missing in the initial migration
    ]
