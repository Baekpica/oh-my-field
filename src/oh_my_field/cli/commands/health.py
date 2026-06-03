from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.health import (
    CapabilityHealthRequest,
    HealthError,
    run_card_workflow,
    run_harden_workflow,
    run_health_workflow,
)


def health(
    capability_name: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    with cli_errors(HealthError):
        request = CapabilityHealthRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            eval_dir=eval_dir,
        )
        summary = run_health_workflow(request)
        emit_json(summary)


def harden(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    with cli_errors(HealthError):
        request = CapabilityHealthRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            eval_dir=eval_dir,
        )
        summary = run_harden_workflow(request)
        emit_json(summary)


def card(
    capability_name: Annotated[str, typer.Argument()],
    write: Annotated[bool, typer.Option("--write")] = False,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    with cli_errors(HealthError):
        summary = run_card_workflow(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            write=write,
        )
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command("health", help="Summarize capability health and next action.")(health)
    app.command(
        "harden",
        help="Recommend the next hardening actions for a capability.",
    )(harden)
    app.command("card", help="Read or rewrite a capability card.")(card)
