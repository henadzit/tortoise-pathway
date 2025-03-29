"""
Models for testing application with model changes after initial migration.
"""

from tortoise import fields, models


class Blog(models.Model):
    """Blog model for testing."""

    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    content = fields.TextField()
    # Changed from original: Added a new field
    summary = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    # Changed from original: Added a new field
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "blogs"

    def __str__(self):
        return self.title


class Tag(models.Model):
    """Tag model for testing."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    # Changed from original: Added a new field
    description = fields.TextField(null=True)

    class Meta:
        table = "tags"

    def __str__(self):
        return self.name


# Changed from original: Added a new model
class Comment(models.Model):
    """Comment model for testing."""

    id = fields.IntField(pk=True)
    blog = fields.ForeignKeyField("test_model_changes.Blog", related_name="comments")
    content = fields.TextField()
    author_name = fields.CharField(max_length=100)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "comments"

    def __str__(self):
        return f"Comment by {self.author_name}"
