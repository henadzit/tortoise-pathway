from typing import Any, Callable, Coroutine, TypeAlias, TypeVar
import argparse
import os

T = TypeVar("T")

Command: TypeAlias = Callable[..., Coroutine[Any, Any, T]]


class Abort(Exception):
    """Custom exception to indicate an abort in the command-line interface."""

    pass


_colors = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    None: "\033[0m",
}

colorize = True


def echo(
    message: str,
    color: str = None,
    nl: bool = True,
) -> None:
    """Print a message to the console with optional color and newline."""
    if colorize and color in _colors:
        message = f"{_colors[color]}{message}{_colors[None]}"
    print(message, end="\n" if nl else "")


# Courtesy of https://gist.github.com/orls/51525c86ee77a56ad396
# Courtesy of https://stackoverflow.com/a/10551190 with env-var retrieval fixed
class EnvDefault(argparse.Action):
    """An argparse action class that auto-sets missing default values from env vars.
    Defaults to requiring the argument."""

    def __init__(self, envvar, required=True, default=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


def env_default(envvar):
    """Sugar for the EnvDefault action."""

    def wrapper(**kwargs):
        return EnvDefault(envvar, **kwargs)

    return wrapper
