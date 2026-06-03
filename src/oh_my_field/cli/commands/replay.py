from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.options import matrix_profiles
from oh_my_field.cli.output import emit_json
from oh_my_field.models import StrictModel
from oh_my_field.replay import ReplayError, ReplayRequest, run_replay_workflow


class ReplayMatrixItem(StrictModel):
    runtime_profile: str
    replay_id: str
    replay_path: str
    harness_status: str


class ReplayMatrixSummary(StrictModel):
    capability_name: str
    results: tuple[ReplayMatrixItem, ...]


def replay(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    execute: Annotated[bool, typer.Option("--execute")] = False,
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 60,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
    allow_env: Annotated[list[str] | None, typer.Option("--allow-env")] = None,
    matrix: Annotated[list[str] | None, typer.Option("--matrix")] = None,
) -> None:
    with cli_errors(ReplayError):
        request = ReplayRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            execute_commands=execute,
            command_cwd=command_cwd,
            command_timeout_seconds=command_timeout_seconds,
            approve_command_risk=approve_command_risk,
            allow_env=tuple(allow_env or ()),
        )
        profiles = matrix_profiles(matrix)
        if profiles:
            results = tuple(
                _replay_matrix_item(request, profile) for profile in profiles
            )
            emit_json(
                ReplayMatrixSummary(capability_name=capability_name, results=results),
            )
            return
        summary = run_replay_workflow(request)
        emit_json(summary)


def _replay_matrix_item(
    request: ReplayRequest,
    runtime_profile: str,
) -> ReplayMatrixItem:
    summary = run_replay_workflow(
        request.model_copy(update={"runtime_profile": runtime_profile}),
    )
    return ReplayMatrixItem(
        runtime_profile=runtime_profile,
        replay_id=summary.replay_id,
        replay_path=summary.replay_path,
        harness_status=summary.harness_status,
    )


def register(app: typer.Typer) -> None:
    app.command(
        "replay",
        help="Replay a capability against its source evidence.",
    )(replay)
