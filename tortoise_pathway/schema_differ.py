"""
Schema difference detection for Tortoise ORM migrations.

This module provides the SchemaDiffer class that detects differences between
Tortoise models and the actual database schema.
"""

from typing import List, Optional, cast

from tortoise import Tortoise
from tortoise.fields.relational import ForeignKeyFieldInstance, ManyToManyFieldInstance
from tortoise.models import Model
from tortoise.indexes import Index

from tortoise_pathway.index_ext import gen_index_name, UniqueIndex
from tortoise_pathway.state import Schema, State
from tortoise_pathway.operations import (
    Operation,
    CreateModel,
    DropModel,
    AddField,
    DropField,
    AlterField,
    AddIndex,
    DropIndex,
)


class SchemaDiffer:
    """Detects differences between Tortoise models and database schema."""

    def __init__(self, app_name: str, state: Optional[State] = None, connection=None):
        """
        Initialize a schema differ for a specific app.

        Args:
            app_name: Name of the app to detect schema changes for
            state: Optional State object containing current state
            connection: Optional database connection
        """
        self.app_name = app_name
        self.connection = connection
        self.state = state or State(app_name)
        self._changes = []

    def get_model_schema(self) -> Schema:
        """Get schema representation from Tortoise models for this app."""
        app_schema: Schema = {"models": {}}

        # Get models for this app only
        if self.app_name in Tortoise.apps:
            app_models = Tortoise.apps[self.app_name]

            for model_name, model in app_models.items():
                if not issubclass(model, Model):
                    continue

                # Get model's DB table name
                table_name = model._meta.db_table

                # Initialize model entry
                app_schema["models"][model_name] = {
                    "table": table_name,
                    "fields": {},
                    "indexes": [],
                }

                # Get fields
                for field_name, field_object in model._meta.fields_map.items():
                    # Skip reverse relations
                    if field_object.__class__.__name__ == "BackwardFKRelation":
                        continue

                    # skip fields that are references to other models, e.g. user_id
                    if field_object.reference is not None:
                        continue

                    # Store the field object directly
                    app_schema["models"][model_name]["fields"][field_name] = field_object

                # Get indexes
                if hasattr(model._meta, "indexes") and isinstance(
                    model._meta.indexes, (list, tuple)
                ):
                    for index in model._meta.indexes:
                        if isinstance(index, Index):
                            if not index.name:
                                # generate index name if not provided
                                index.name = gen_index_name(
                                    "idx", model._meta.db_table, index.fields
                                )
                            app_schema["models"][model_name]["indexes"].append(index)
                        elif isinstance(index, (list, tuple)):
                            app_schema["models"][model_name]["indexes"].append(
                                Index(
                                    fields=index,
                                    name=gen_index_name("idx", model._meta.db_table, index),
                                )
                            )
                        else:
                            raise ValueError(
                                f"Unknown index type {type(index)} for model {model_name}"
                            )

                # Get unique constraints
                if hasattr(model._meta, "unique_together"):
                    for unique_fields in model._meta.unique_together:
                        app_schema["models"][model_name]["indexes"].append(
                            UniqueIndex(
                                fields=unique_fields,
                                name=gen_index_name("uniq", model._meta.db_table, unique_fields),
                            )
                        )

        return app_schema

    async def _detect_create_models(self, current_schema: Schema, model_schema: Schema):
        """
        Detect models that need to be created (models in the model schema but not in the current schema).

        Args:
            current_schema: Schema from the current state
            model_schema: Schema derived from Tortoise models

        Returns:
            List of CreateModel operations
        """
        processed_model_names = []
        models_to_create = sorted(
            list(set(model_schema["models"].keys()) - set(current_schema["models"].keys()))
        )

        # Tables to create (in models but not in current schema)
        retries = 0
        while len(models_to_create) > 0:
            model_name = models_to_create.pop(0)
            model_info = model_schema["models"][model_name]
            # filtering out ManyToManyFieldInstance to add them after table creation
            field_objects = {
                n: f
                for n, f in model_info["fields"].items()
                if not isinstance(f, ManyToManyFieldInstance)
            }

            # The following code ensures that the referenced models are created before
            # the model that references them. Otherwise, we won't be able to create
            # foreign key constraints.
            try_again = False
            for field in field_objects.values():
                if isinstance(field, ForeignKeyFieldInstance):
                    referenced_model_name = field.model_name.split(".")[-1]
                    if (
                        referenced_model_name not in current_schema["models"]
                        and referenced_model_name not in processed_model_names
                    ):
                        # The referenced model has not been created yet, so we need to try again later
                        models_to_create.append(model_name)
                        try_again = True
                        break

            if try_again:
                retries += 1
                if retries > 50:
                    raise ValueError(f"Possible circular dependency to {models_to_create}")
                continue

            model_ref = f"{self.app_name}.{model_name}"
            self._changes.append(
                CreateModel(
                    model=model_ref,
                    table=model_info["table"],
                    fields=field_objects,
                )
            )

            # Add separate AddIndex operations for each index
            for index in model_info["indexes"]:
                self._changes.append(
                    AddIndex(
                        model=model_ref,
                        index=index,
                    )
                )

            processed_model_names.append(model_name)

        # When Tortoise initialized, the M2M field is present on the both models. We need to add just
        # a single operation to setup the M2M relation, hence we need to skip one side of the relation.
        for model_name in processed_model_names:
            model_info = model_schema["models"][model_name]
            for field_name, field_object in model_info["fields"].items():
                if not isinstance(field_object, ManyToManyFieldInstance):
                    continue

                field = cast(ManyToManyFieldInstance, field_object)

                if self._is_m2m_processed_from_the_other_side(
                    f"{self.app_name}.{model_name}", field.model_name, field.through
                ):
                    continue

                self._changes.append(
                    AddField(
                        model=f"{self.app_name}.{model_name}",
                        field_object=field,
                        field_name=field_name,
                    )
                )

    async def _detect_drop_models(
        self,
        current_schema: Schema,
        model_schema: Schema,
    ):
        """
        Detect models that need to be dropped (models in the current schema but not in the model schema).

        Args:
            current_schema: Schema from the current state
            model_schema: Schema derived from Tortoise models

        Returns:
            List of DropModel operations
        """
        # Tables to drop (in current schema but not in models)
        for model_name in sorted(
            set(current_schema["models"].keys()) - set(model_schema["models"].keys())
        ):
            model_ref = f"{self.app_name}.{model_name}"
            self._changes.append(
                DropModel(
                    model=model_ref,
                )
            )

    async def _detect_field_changes(
        self,
        current_schema: Schema,
        model_schema: Schema,
    ):
        """
        Detect field and index changes for models that exist in both schemas.

        Args:
            current_schema: Schema from the current state
            model_schema: Schema derived from Tortoise models

        Returns:
            List of field and index related operations
        """
        # For tables that exist in both
        for model_name in sorted(
            set(current_schema["models"].keys()) & set(model_schema["models"].keys())
        ):
            # Get the model info for both
            current_model = current_schema["models"][model_name]
            model_model = model_schema["models"][model_name]

            # Get field sets for comparison
            current_fields = current_model["fields"]
            model_fields = model_model["fields"]

            # Map of field names between current schema and model
            current_field_names = set(current_fields.keys())
            model_field_names = set(model_fields.keys())

            # Reference to the model
            model_ref = f"{self.app_name}.{model_name}"

            # Fields to add (in model but not in current schema)
            for field_name in sorted(model_field_names - current_field_names):
                field_obj = model_fields[field_name]

                if isinstance(field_obj, ManyToManyFieldInstance):
                    m2m_field = cast(ManyToManyFieldInstance, field_obj)
                    if self._is_m2m_processed_from_the_other_side(
                        model_ref, m2m_field.model_name, m2m_field.through
                    ):
                        continue

                self._changes.append(
                    AddField(
                        model=model_ref,
                        field_object=field_obj,
                        field_name=field_name,
                    )
                )

            # Fields to drop (in current schema but not in model)
            for field_name in sorted(current_field_names - model_field_names):
                self._changes.append(
                    DropField(
                        model=model_ref,
                        field_name=field_name,
                    )
                )

            # Fields to alter (in both, but might be different)
            for field_name in sorted(current_field_names & model_field_names):
                current_field = current_fields[field_name]
                model_field = model_fields[field_name]

                # Check if fields are different
                if self._are_fields_different(current_field, model_field):
                    self._changes.append(
                        AlterField(
                            model=model_ref,
                            field_object=model_field,
                            field_name=field_name,
                        )
                    )

    async def _detect_index_changes(
        self,
        current_schema: Schema,
        model_schema: Schema,
    ):
        for model_name in sorted(
            set(current_schema["models"].keys()) & set(model_schema["models"].keys())
        ):
            model_ref = f"{self.app_name}.{model_name}"

            current_model = current_schema["models"][model_name]
            model_model = model_schema["models"][model_name]

            # Get indexes from both current schema and model schema
            current_indexes = current_model.get("indexes", [])
            model_indexes = model_model.get("indexes", [])

            # Create maps of index names for easier comparison
            current_index_map = {idx.name: idx for idx in current_indexes}
            model_index_map = {idx.name: idx for idx in model_indexes}


            # Indexes to add (in model but not in current schema)
            for index_name in set(model_index_map.keys()) - set(current_index_map.keys()):
                index = model_index_map[index_name]
                self._changes.append(
                    AddIndex(
                        model=model_ref,
                        index=index,
                    )
                )

            # Indexes to drop (in current schema but not in model)
            for index_name in set(current_index_map.keys()) - set(model_index_map.keys()):
                self._changes.append(
                    DropIndex(
                        model=model_ref,
                        index_name=index_name,
                    )
                )

            # Indexes to alter (in both, but different)
            for index_name in set(current_index_map.keys()) & set(model_index_map.keys()):
                current_index = current_index_map[index_name]
                model_index = model_index_map[index_name]

                # Check if indexes are different
                if (
                    isinstance(current_index, UniqueIndex) != isinstance(model_index, UniqueIndex)
                    or current_index.fields != model_index.fields
                ):
                    # First drop the old index
                    self._changes.append(
                        DropIndex(
                            model=model_ref,
                            index_name=index_name,
                        )
                    )

                    # Then add the new index
                    self._changes.append(
                        AddIndex(
                            model=model_ref,
                            index=model_index,
                        )
                    )

    async def detect_changes(self) -> List[Operation]:
        """
        Detect schema changes between models and state derived from migrations.

        Returns:
            List of Operation objects representing the detected changes.
        """
        self._changes = []
        current_schema = self.state.get_schema()
        model_schema = self.get_model_schema()

        # Collect changes from each detection method
        await self._detect_create_models(current_schema, model_schema)
        await self._detect_drop_models(current_schema, model_schema)
        await self._detect_field_changes(current_schema, model_schema)
        await self._detect_index_changes(current_schema, model_schema)
        return self._changes

    def _are_fields_different(self, field1, field2) -> bool:
        """
        Compare two Field objects to determine if they are effectively different.

        Args:
            field1: First Field object
            field2: Second Field object

        Returns:
            True if the fields are different (require migration), False otherwise
        """
        # Check if they're the same class type
        if field1.__class__.__name__ != field2.__class__.__name__:
            return True

        # Check key field attributes that would require a migration
        important_attrs = [
            "null",
            "default",
            "pk",
            "unique",
            "index",
            "max_length",
            "description",
            "constraint_name",
            "reference",
            # TODO: in Tortoise, if auto_now_add=True, auto_now is also True, however, you cann set both to True.
            # We need to handle auto_now separately.
            # "auto_now",
            "auto_now_add",
        ]

        # For more strict comparison
        for attr in important_attrs:
            if (hasattr(field1, attr) and not hasattr(field2, attr)) or (
                not hasattr(field1, attr) and hasattr(field2, attr)
            ):
                return True

            if hasattr(field1, attr) and hasattr(field2, attr):
                val1 = getattr(field1, attr)
                val2 = getattr(field2, attr)
                if val1 != val2:
                    return True

        # For RelationalField objects, check additional attributes
        if hasattr(field1, "model_name") and hasattr(field2, "model_name"):
            if getattr(field1, "model_name") != getattr(field2, "model_name"):
                return True

            # Check related_name
            related_name1 = getattr(field1, "related_name", None)
            related_name2 = getattr(field2, "related_name", None)
            if related_name1 != related_name2:
                return True

        # Fields are effectively the same for migration purposes
        return False

    def _is_m2m_processed_from_the_other_side(
        self,
        referring_model_ref: str,
        referred_model_ref: str,
        through_table: str,
    ) -> bool:
        """
        Check if the M2M relation has been processed from the other side.
        This is to avoid adding the same M2M relation twice.
        """
        for change in self._changes:
            if not isinstance(change, AddField):
                continue

            if not isinstance(change.field_object, ManyToManyFieldInstance):
                continue

            field = cast(ManyToManyFieldInstance, change.field_object)

            if (
                change.model == referred_model_ref
                and field.model_name == referring_model_ref
                and field.through == through_table
            ):
                return True
        return False
