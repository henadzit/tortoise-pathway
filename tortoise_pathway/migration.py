from pathlib import Path

from tortoise_pathway.operations import Operation


class Migration:
    """Base class for all migrations."""

    dependencies: list[tuple[str, str]]
    operations: list[Operation]
    app_name: str | None = None

    @classmethod
    def name(cls) -> str:
        """
        Return the name of the migration based on its module location.

        The name is extracted from the module name where this migration class is defined.
        """
        module = cls.__module__
        return module.split(".")[-1]

    @classmethod
    def path(cls) -> Path:
        """
        Return the path to the migration file relative to the current working directory.

        Uses the module information to determine the file location.
        """
        module = cls.__module__
        module_path = module.replace(".", "/")
        return Path(f"{module_path}.py")

    @classmethod
    def display_name(cls) -> str:
        return f"{cls.app_name} -> {cls.name()}"
