from collections.abc import Generator
from contextlib import contextmanager

import typer
from pydantic import ValidationError

from oh_my_field.infrastructure.fs.storage import StorageError


@contextmanager
def cli_errors(*error_types: type[Exception]) -> Generator[None]:
    """Map workflow errors to a stderr message and exit code 1.

    ``StorageError`` and ``ValidationError`` are always handled because every
    command persists artifacts and validates request models. Pass any command
    specific error types (``PromoteError``, ``EvalError`` ...) as positionals.
    """
    handled: tuple[type[Exception], ...] = (
        StorageError,
        ValidationError,
        *error_types,
    )
    try:
        yield
    except handled as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
