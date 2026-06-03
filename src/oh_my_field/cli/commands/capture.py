from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.capture import (
    CaptureError,
    CaptureRequest,
    run_capture_workflow,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.options import capture_file_inputs
from oh_my_field.cli.output import emit_json


def capture(
    goal: Annotated[str, typer.Option("--goal")],
    prompt: Annotated[list[Path] | None, typer.Option("--prompt")] = None,
    context: Annotated[list[Path] | None, typer.Option("--context")] = None,
    tool_call: Annotated[list[Path] | None, typer.Option("--tool-call")] = None,
    command_output: Annotated[
        list[Path] | None,
        typer.Option("--command-output"),
    ] = None,
    diff: Annotated[list[Path] | None, typer.Option("--diff")] = None,
    test_result: Annotated[
        list[Path] | None,
        typer.Option("--test-result"),
    ] = None,
    artifact: Annotated[list[Path] | None, typer.Option("--artifact")] = None,
    command: Annotated[list[str] | None, typer.Option("--command")] = None,
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
    feedback: Annotated[list[str] | None, typer.Option("--feedback")] = None,
    user_intervention: Annotated[
        list[str] | None,
        typer.Option("--user-intervention"),
    ] = None,
    final_artifact: Annotated[
        list[str] | None,
        typer.Option("--final-artifact"),
    ] = None,
    improvement_note: Annotated[
        list[str] | None,
        typer.Option("--improvement-note"),
    ] = None,
    outcome: Annotated[
        Literal["success", "failure", "unknown"],
        typer.Option("--outcome"),
    ] = "unknown",
    runtime_tool: Annotated[
        list[str] | None,
        typer.Option("--runtime-tool"),
    ] = None,
    retries: Annotated[int, typer.Option("--retries")] = 0,
    field: Annotated[str, typer.Option("--field")] = "local",
    runtime: Annotated[str, typer.Option("--runtime")] = "codex",
    model: Annotated[str | None, typer.Option("--model")] = None,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    request = CaptureRequest(
        goal=goal,
        field=field,
        runtime=runtime,
        model=model,
        runtime_tools=tuple(runtime_tool or ()),
        evidence_dir=evidence_dir,
        files=(
            *capture_file_inputs("prompt", prompt),
            *capture_file_inputs("context", context),
            *capture_file_inputs("tool_call", tool_call),
            *capture_file_inputs("command_output", command_output),
            *capture_file_inputs("diff", diff),
            *capture_file_inputs("test_result", test_result),
            *capture_file_inputs("artifact", artifact),
        ),
        commands=tuple(command or ()),
        command_cwd=command_cwd,
        command_timeout_seconds=command_timeout_seconds,
        approve_command_risk=approve_command_risk,
        allow_env=tuple(allow_env or ()),
        retries=retries,
        feedback=tuple(feedback or ()),
        user_interventions=tuple(user_intervention or ()),
        final_artifacts=tuple(final_artifact or ()),
        improvement_notes=tuple(improvement_note or ()),
        success_or_failure_label=outcome,
    )
    with cli_errors(CaptureError):
        summary = run_capture_workflow(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "capture",
        help="Capture files, commands, and feedback as evidence.",
    )(capture)
