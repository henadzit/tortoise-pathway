"""
Initial migration for test_model_changes app
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.operations import CreateModel
from tortoise.fields.data import CharField
from tortoise.fields.data import DatetimeField
from tortoise.fields.data import IntField
from tortoise.fields.data import TextField
from tortoise.fields.relational import ForeignKeyField

class InitialMigration(Migration):
    """
    Initial migration creating blogs and tags tables.
    """

    dependencies = []
    operations = [
        CreateModel(
            model="test_model_changes.Blog",
            table="blogs",
            fields={
                "id": IntField(primary_key=True),
                "slug": CharField(max_length=255),
                "title": CharField(max_length=255),
                "content": TextField(),
                "created_at": DatetimeField(auto_now_add=True),
                # Note: summary and updated_at fields are missing in the initial migration
            },
        ),
        CreateModel(
            model="test_model_changes.Tag",
            table="tags",
            fields={
                "id": IntField(primary_key=True),
                "name": CharField(max_length=50),
                "color": CharField(max_length=50),
                "blog": ForeignKeyField(
                    "test_model_changes.Blog", related_name="tags", source_field="blog_id"
                ),
                # Note: description field is missing in the initial migration
            },
        ),
        # Note: Comment model is missing in the initial migration
    ]
