"""
Models for testing application with applied migrations.
"""

from tortoise import fields, models


class Product(models.Model):
    """Product model for testing."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField()
    price = fields.DecimalField(max_digits=10, decimal_places=2)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "products"

    def __str__(self):
        return self.name


class Category(models.Model):
    """Category model for testing."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)

    class Meta:
        table = "categories"

    def __str__(self):
        return self.name
