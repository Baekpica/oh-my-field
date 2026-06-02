from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from oh_my_field.capture import (
    CaptureError,
    CaptureFileInput,
    CaptureRequest,
    run_capture_workflow,
)
from oh_my_field.models import CapturedFileRole
from oh_my_field.promote import PromoteError, PromoteRequest, run_promote_workflow
from oh_my_field.storage import StorageError

app = typer.Typer(
    help="oh-my-field turns tacit know-how into reusable capabilities.",
    no_args_is_help=True,
)


def _main() -> None:
    pass


app.callback()(_main)


def _capture(
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
    feedback: Annotated[list[str] | None, typer.Option("--feedback")] = None,
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
        evidence_dir=evidence_dir,
        files=(
            *_capture_file_inputs("prompt", prompt),
            *_capture_file_inputs("context", context),
            *_capture_file_inputs("tool_call", tool_call),
            *_capture_file_inputs("command_output", command_output),
            *_capture_file_inputs("diff", diff),
            *_capture_file_inputs("test_result", test_result),
            *_capture_file_inputs("artifact", artifact),
        ),
        feedback=tuple(feedback or ()),
    )
    try:
        summary = run_capture_workflow(request)
    except (CaptureError, StorageError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _capture_file_inputs(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[CaptureFileInput, ...]:
    return tuple(CaptureFileInput(role=role, path=path) for path in paths or ())


app.command("capture")(_capture)


def _promote(
    evidence_id: Annotated[str, typer.Argument()],
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = run_promote_workflow(
            PromoteRequest(
                evidence_id=evidence_id,
                name=name,
                description=description,
                version=version,
                evidence_dir=evidence_dir,
                capabilities_dir=capabilities_dir,
            ),
        )
    except (PromoteError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("promote")(_promote)
