from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.reflect import (
    ReflectError,
    ReflectRequest,
    run_reflect_workflow,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
)


def reflect(
    capability_name: Annotated[str, typer.Argument()],
    eval_id: Annotated[str | None, typer.Option("--eval-id")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
) -> None:
    with cli_errors(ReflectError):
        request = ReflectRequest(
            capability_name=capability_name,
            eval_id=eval_id,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            eval_dir=eval_dir,
            reflection_dir=reflection_dir,
            notes=tuple(note or ()),
        )
        summary = run_reflect_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "reflect",
        help="Generate a reflection report from evidence and evals.",
    )(reflect)
