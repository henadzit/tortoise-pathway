"""
State tracking for migration operations.

This module provides the State class that manages the state of the models based
on applied migrations, rather than the actual database state.
"""

import copy
from typing import Dict, List, Tuple, TypedDict, cast

from tortoise.fields import Field
from tortoise.fields.relational import ManyToManyFieldInstance
from tortoise.indexes import Index

from tortoise_pathway.operations import (
    Operation,
    CreateModel,
    DropModel,
    RenameModel,
    AddField,
    DropField,
    AlterField,
    RenameField,
    AddIndex,
    DropIndex,
)


class ModelSchema(TypedDict):
    table: str
    fields: Dict[str, Field]
    indexes: List[Index]


class AppSchema(TypedDict):
    models: Dict[str, ModelSchema]


Schema = Dict[str, AppSchema]


class State:
    """
    Represents the state of the models based on applied migrations.

    This class is used to track the expected database schema state based on
    the migrations that have been applied, rather than querying the actual
    database schema directly.

    Attributes:
        schema: Dictionary mapping model names to their schema representations.
    """

    def __init__(self, schema: Schema | None = None):
        """
        Initialize an empty state.

        Args:
            schema: The tortoise configuration.
        """
        self._schema: Schema = schema or {}
        self._snapshots: List[Tuple[str, State]] = []

    def apply_operation(self, operation: Operation) -> None:
        """
        Apply a single schema change operation to the state.

        Args:
            operation: The Operation object to apply.
        """

        # Handle each type of operation
        if isinstance(operation, CreateModel):
            self._apply_create_model(operation)
        elif isinstance(operation, DropModel):
            self._apply_drop_model(operation)
        elif isinstance(operation, RenameModel):
            self._apply_rename_model(operation)
        elif isinstance(operation, AddField):
            self._apply_add_field(operation)
        elif isinstance(operation, DropField):
            self._apply_drop_field(operation)
        elif isinstance(operation, AlterField):
            self._apply_alter_field(operation)
        elif isinstance(operation, RenameField):
            self._apply_rename_field(operation)
        elif isinstance(operation, AddIndex):
            self._apply_add_index(operation)
        elif isinstance(operation, DropIndex):
            self._apply_drop_index(operation)

    def snapshot(self, name: str) -> None:
        """
        Take a snapshot of the current state.

        Args:
            name: The name of the snapshot.
        """
        self._snapshots.append((name, copy.deepcopy(self)))

    def prev(self) -> "State":
        """
        Get the previous state.
        """
        if len(self._snapshots) == 1:
            return State()
        _, state = self._snapshots[-2]
        return state

    def _get_app_models(
        self, app_name: str, create: bool = False
    ) -> Dict[str, ModelSchema]:
        if app_name not in self._schema:
            if not create:
                raise KeyError(f"App {app_name} not found in schema")
            self._schema[app_name] = {"models": {}}

        return self._schema[app_name]["models"]

    def _apply_create_model(self, operation: CreateModel) -> None:
        """Apply a CreateModel operation to the state."""
        # Create a new model entry
        app_models = self._get_app_models(operation.app_name, create=True)
        app_models[operation.model_name] = {
            "table": operation.table,
            "fields": operation.fields.copy(),
            "indexes": [],
        }

    def _apply_drop_model(self, operation: DropModel) -> None:
        """Apply a DropModel operation to the state."""
        app_models = self._get_app_models(operation.app_name)
        # Remove the model if it exists
        if operation.model_name in app_models:
            del app_models[operation.model_name]

    def _apply_rename_model(self, operation: RenameModel) -> None:
        """Apply a RenameModel operation to the state."""
        app_models = self._get_app_models(operation.app_name)
        model = app_models[operation.model_name]

        if operation.new_table_name:
            model["table"] = operation.new_table_name

        if operation.new_model_name:
            del app_models[operation.model_name]
            app_models[operation.new_model_name] = model

    def _apply_add_field(self, operation: AddField) -> None:
        """Apply an AddField operation to the state."""
        model_name = operation.model_name
        field_obj = operation.field_object
        field_name = operation.field_name
        # Add the field directly to the state
        app_models = self._get_app_models(operation.app_name)
        app_models[model_name]["fields"][field_name] = field_obj

        # m2m fields are bidirectional, so we need to add the field to the referred model
        if isinstance(field_obj, ManyToManyFieldInstance):
            m2m_field = cast(ManyToManyFieldInstance, field_obj)
            referred_model_app, referred_model_name = Operation._split_model_reference(
                m2m_field.model_name
            )
            referred_app_models = self._get_app_models(referred_model_app)
            referred_app_models[referred_model_name]["fields"][
                m2m_field.related_name
            ] = ManyToManyFieldInstance(
                model_name=f"{operation.app_name}.{operation.model_name}",
                through=m2m_field.through,
                related_name=field_name,
                on_delete=m2m_field.on_delete,
            )

    def _apply_drop_field(self, operation: DropField) -> None:
        """Apply a DropField operation to the state."""
        field_name = operation.field_name

        model_fields = self.get_fields(operation.app_name, operation.model_name)

        # Remove the field from the state
        if field_name in model_fields:
            del model_fields[field_name]

    def _apply_alter_field(self, operation: AlterField) -> None:
        """Apply an AlterField operation to the state."""
        field_name = operation.field_name
        field_obj = operation.field_object

        model_fields = self.get_fields(operation.app_name, operation.model_name)

        # Verify the field exists
        if field_name in model_fields:
            # Replace with the new field object
            model_fields[field_name] = field_obj

    def _apply_rename_field(self, operation: RenameField) -> None:
        """Apply a RenameField operation to the state."""
        old_field_name = operation.field_name
        new_field_name = operation.new_field_name

        model_fields = self.get_fields(operation.app_name, operation.model_name)

        field_obj = model_fields[old_field_name]
        if new_field_name:
            model_fields[new_field_name] = field_obj
            del model_fields[old_field_name]
        if operation.new_column_name:
            field_obj.source_field = operation.new_column_name

    def _apply_add_index(self, operation: AddIndex) -> None:
        """Apply an AddIndex operation to the state."""
        model = self.get_model(operation.app_name, operation.model_name)
        model["indexes"].append(operation.index)

    def _apply_drop_index(self, operation: DropIndex) -> None:
        """Apply a DropIndex operation to the state."""
        model = self.get_model(operation.app_name, operation.model_name)
        for i, index in enumerate(model["indexes"]):
            if index.name == operation.index_name:
                del model["indexes"][i]
                return

        raise KeyError(
            f"Index {operation.index_name} not found in {operation.model_name}"
        )

    def get_schema(self) -> Schema:
        """Get the entire schema representation."""
        return self._schema

    def get_model(self, app_name: str, model_name: str) -> ModelSchema:
        """
        Get a specific model for this app.

        Returns:
            Dictionary of the model.
        """
        app_models = self._get_app_models(app_name)
        if model_name not in app_models:
            raise KeyError(f"Model {model_name} not found in app {app_name}")
        return app_models[model_name]

    def get_table_name(self, app_name: str, model_name: str) -> str:
        """
        Get the table name for a specific model.

        Args:
            model: The model name.

        Returns:
            The table name, or None if not found.
        """
        return self._schema[app_name]["models"][model_name]["table"]

    def get_field(self, app_name: str, model_name: str, field_name: str) -> Field:
        """
        Get the field object for a specific field.
        """
        fields = self.get_fields(app_name, model_name)
        if field_name not in fields:
            raise KeyError(f"Field {field_name} not found in {model_name}")
        return fields[field_name]

    def get_index(self, app_name: str, model_name: str, index_name: str) -> Index:
        """
        Get the Index object by name.
        """
        model = self.get_model(app_name, model_name)
        for index in model["indexes"]:
            if index.name == index_name:
                return index
        raise KeyError(f"Index {index_name} not found in {model_name}")

    def get_fields(self, app_name: str, model_name: str) -> Dict[str, Field]:
        """
        Get all fields for a specific model.

        Args:
            model_name: The model name.

        Returns:
            Dictionary mapping field names to Field objects, or None if model not found.
        """
        model = self.get_model(app_name, model_name)
        return model["fields"]

    def get_column_name(self, app_name: str, model_name: str, field_name: str) -> str:
        """
        Get the column name for a specific field.

        Args:
            model_name: The model name.
            field_name: The field name.

        Returns:
            The column name, or None if not found.
        """
        fields = self.get_fields(app_name, model_name)
        try:
            if field_name in fields:
                field_obj = fields[field_name]
                # Get source_field if available, otherwise use field_name as the column name
                source_field = getattr(field_obj, "source_field", None)
                if source_field is not None:
                    return source_field
        except (KeyError, TypeError):
            pass  # Fall back to using field name as column name

        return field_name
