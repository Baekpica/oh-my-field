from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.diff_artifacts import (
    DiffError,
    DiffRequest,
    compare_artifacts,
)
from oh_my_field.cli.errors import cli_errors


def diff_artifacts(
    target_type: Annotated[
        Literal["evidence", "capability", "harness", "learning-patch"],
        typer.Argument(),
    ],
    left: Annotated[str, typer.Argument()],
    right: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    from_capabilities_dir: Annotated[
        Path | None,
        typer.Option("--from-capabilities-dir"),
    ] = None,
    to_capabilities_dir: Annotated[
        Path | None,
        typer.Option("--to-capabilities-dir"),
    ] = None,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
) -> None:
    with cli_errors(DiffError):
        summary = compare_artifacts(
            DiffRequest(
                target_type=target_type,
                left=left,
                right=right,
                capabilities_dir=capabilities_dir,
                from_capabilities_dir=from_capabilities_dir,
                to_capabilities_dir=to_capabilities_dir,
                evidence_dir=evidence_dir,
                learning_patch_dir=learning_patch_dir,
            ),
        )
        typer.echo(summary.diff_text, nl=False)


def register(app: typer.Typer) -> None:
    app.command(
        "diff",
        help="Show a unified diff between OMF artifacts.",
    )(diff_artifacts)
