from pathlib import Path
from typing import List

from tortoise_pathway.operations import Operation


class Migration:
    """Base class for all migrations."""

    dependencies: List[str] = []
    operations: List[Operation] = []

    @classmethod
    def name(cls) -> str:
        """
        Return the name of the migration based on its module location.

        The name is extracted from the module name where this migration class is defined.
        """
        module = cls.__module__
        # Get the filename which is the last part of the module path
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
