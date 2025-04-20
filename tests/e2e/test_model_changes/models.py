"""
Models for testing application with model changes after initial migration.
"""

from tortoise import fields, models


class Blog(models.Model):
    """Existing model"""

    id = fields.IntField(primary_key=True)
    # Changed from original: Added unique=True
    slug = fields.CharField(max_length=255, unique=True)
    title = fields.CharField(max_length=255)
    # Changed from original: Removed the 'content' field to simulate field deletion
    # content = fields.TextField()
    # Changed from original: Added a new field
    summary = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    # Changed from original: Added a new field
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "blogs"
        # Changed from original: Added a new index
        indexes = [("created_at",)]

    def __str__(self):
        return self.title


class Tag(models.Model):
    """Existing model"""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50, unique=True)
    # Changed: added null=True and default="red"
    color = fields.CharField(max_length=50, null=True, default="red")
    # Changed from original: Added a new field
    description = fields.TextField(null=True)

    class Meta:
        table = "tags"

    def __str__(self):
        return self.name


# Changed from original: Added a new model
class Comment(models.Model):
    """New model"""

    id = fields.IntField(primary_key=True)
    blog = fields.ForeignKeyField("test_model_changes.Blog", related_name="comments")
    content = fields.TextField()
    author_name = fields.CharField(max_length=100)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "comments"

    def __str__(self):
        return f"Comment by {self.author_name}"
