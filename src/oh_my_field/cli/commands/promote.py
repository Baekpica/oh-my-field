from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.promote import (
    PromoteError,
    PromoteRequest,
    run_promote_workflow,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
)


def promote(
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
    evidence_id: Annotated[str | None, typer.Argument()] = None,
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    from_evidence_set: Annotated[
        Path | None,
        typer.Option("--from-evidence-set"),
    ] = None,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = DEFAULT_EVAL_DIR,
    capabilities_dir: Annotated[
        Path, typer.Option("--capabilities-dir")
    ] = DEFAULT_CAPABILITIES_DIR,
) -> None:
    with cli_errors(PromoteError):
        request = PromoteRequest(
            evidence_id=evidence_id,
            from_evidence_set=from_evidence_set,
            name=name,
            description=description,
            version=version,
            evidence_dir=evidence_dir,
            eval_dir=eval_dir,
            capabilities_dir=capabilities_dir,
        )
        summary = run_promote_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "promote",
        help="Promote evidence or an evidence set into a capability.",
    )(promote)
