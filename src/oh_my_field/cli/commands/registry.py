from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.registry import (
    RegistryError,
    RegistryRequest,
    run_registry_workflow,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json


def registry(
    capability_name: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    with cli_errors(RegistryError):
        request = RegistryRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            eval_dir=eval_dir,
        )
        summary = run_registry_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "registry",
        help="List capability registry health and metadata.",
    )(registry)
