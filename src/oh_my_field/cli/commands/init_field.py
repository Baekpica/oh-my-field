from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.init_field import InitFieldRequest, initialize_field
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR


def init_field(
    runtime: Annotated[str, typer.Option("--runtime")] = "codex",
    model: Annotated[str | None, typer.Option("--model")] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
) -> None:
    summary = initialize_field(
        InitFieldRequest(
            runtime=runtime,
            model=model,
            capabilities_dir=capabilities_dir,
        ),
    )
    emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command("init", help="Initialize the current project as an OMF field.")(
        init_field,
    )
