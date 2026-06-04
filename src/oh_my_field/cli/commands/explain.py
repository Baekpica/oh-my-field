from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.explain_artifacts import (
    ExplainError,
    ExplainRequest,
    explain_artifact,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json

ExplainTarget = Literal["capability", "harness", "learning-patch"]


def explain_command(
    target_type: Annotated[ExplainTarget, typer.Argument()],
    target_id: Annotated[str, typer.Argument()],
    rule: Annotated[str | None, typer.Option("--rule")] = None,
    check: Annotated[str | None, typer.Option("--check")] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
) -> None:
    with cli_errors(ExplainError, ValueError):
        summary = explain_artifact(
            ExplainRequest(
                target_type=target_type,
                target_id=target_id,
                rule=rule,
                check=check,
                capabilities_dir=capabilities_dir,
                learning_patch_dir=learning_patch_dir,
            ),
        )
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command("explain", help="Explain why an OMF rule or patch exists.")(
        explain_command,
    )
    app.command("why", help="Alias for explain.")(explain_command)
