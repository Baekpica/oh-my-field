from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.inspection import InspectRequest
from oh_my_field.application.inspection import inspect_artifact as run_inspect
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json


def inspect_command(
    target_type: Annotated[
        Literal[
            "evidence",
            "capability",
            "replay",
            "eval",
            "export",
            "import",
            "run",
            "workflow",
            "context",
            "learning",
            "reflection",
        ],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    export_dir: Annotated[Path, typer.Option("--export-dir")] = Path(".omf/exports"),
    target: Annotated[str | None, typer.Option("--target")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
) -> None:
    with cli_errors(ValueError):
        request = InspectRequest(
            target_type=target_type,
            target_id=target_id,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            eval_dir=eval_dir,
            workflow_dir=workflow_dir,
            context_dir=context_dir,
            learning_dir=learning_dir,
            reflection_dir=reflection_dir,
            export_dir=export_dir,
            target=target,
            model=model,
        )
        summary = run_inspect(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command("inspect", help="Inspect a stored oh-my-field artifact.")(
        inspect_command,
    )
