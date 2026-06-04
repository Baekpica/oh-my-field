from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.context import (
    ContextError,
    ContextRequest,
    run_context_workflow,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json


def context(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    include_optional: Annotated[bool, typer.Option("--include-optional")] = False,
    query: Annotated[str | None, typer.Option("--query")] = None,
    max_chars: Annotated[int | None, typer.Option("--max-chars")] = None,
) -> None:
    with cli_errors(ContextError):
        request = ContextRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            context_dir=context_dir,
            include_optional=include_optional,
            query=query,
            max_chars=max_chars,
        )
        summary = run_context_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "context",
        help="Build a context bundle from capability policy.",
    )(context)
