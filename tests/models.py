"""
Common models for tests.
"""

from tortoise import models, fields


class TestModel(models.Model):
    """Test model for schema operations."""

    __test__ = False

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)

    class Meta:
        table = "test_table"
