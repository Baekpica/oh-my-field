from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.export import ExportError, ExportRequest, run_export_workflow


def export(
    capability_name: Annotated[str, typer.Argument()],
    approve_export: Annotated[
        bool,
        typer.Option("--approve-export"),
    ] = False,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    export_dir: Annotated[Path, typer.Option("--export-dir")] = Path(
        ".omf/exports",
    ),
) -> None:
    with cli_errors(ExportError):
        request = ExportRequest(
            capability_name=capability_name,
            approve_export=approve_export,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            eval_dir=eval_dir,
            context_dir=context_dir,
            learning_dir=learning_dir,
            reflection_dir=reflection_dir,
            export_dir=export_dir,
        )
        summary = run_export_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "export",
        help="Export a capability bundle after explicit approval.",
    )(export)
