from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.application.import_run import (
    AdapterError,
    AgentArtifactInput,
    AgentImportRequest,
    import_agent_run,
)
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.models import CapturedFileRole


def import_run(
    adapter: Annotated[str, typer.Argument()],
    log_path: Annotated[Path, typer.Option("--log")],
    goal: Annotated[str, typer.Option("--goal")],
    diff: Annotated[list[Path] | None, typer.Option("--diff")] = None,
    test_result: Annotated[
        list[Path] | None,
        typer.Option("--test-result"),
    ] = None,
    command_output: Annotated[
        list[Path] | None,
        typer.Option("--command-output"),
    ] = None,
    artifact: Annotated[list[Path] | None, typer.Option("--artifact")] = None,
    artifact_root: Annotated[
        list[Path] | None,
        typer.Option("--artifact-root"),
    ] = None,
    field: Annotated[str, typer.Option("--field")] = "local",
    model: Annotated[str | None, typer.Option("--model")] = None,
    max_artifact_bytes: Annotated[
        int | None,
        typer.Option("--max-artifact-bytes"),
    ] = None,
    max_artifact_count: Annotated[
        int | None,
        typer.Option("--max-artifact-count"),
    ] = None,
    max_total_artifact_bytes: Annotated[
        int | None,
        typer.Option("--max-total-artifact-bytes"),
    ] = None,
    exclude: Annotated[list[str] | None, typer.Option("--exclude")] = None,
    outcome: Annotated[
        Literal["success", "failure", "unknown"],
        typer.Option("--outcome"),
    ] = "unknown",
    redact_secrets: Annotated[
        bool,
        typer.Option("--redact-secrets/--no-redact-secrets"),
    ] = True,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    with cli_errors(AdapterError):
        request = AgentImportRequest(
            adapter=adapter,
            log_path=log_path,
            goal=goal,
            field=field,
            model=model,
            evidence_dir=evidence_dir,
            artifacts=(
                *_agent_artifacts("diff", diff),
                *_agent_artifacts("test_result", test_result),
                *_agent_artifacts("command_output", command_output),
                *_agent_artifacts("artifact", artifact),
            ),
            artifact_roots=tuple(artifact_root or ()),
            max_artifact_bytes=max_artifact_bytes,
            max_artifact_count=max_artifact_count,
            max_total_artifact_bytes=max_total_artifact_bytes,
            exclude_patterns=tuple(exclude or ()),
            redact_secrets=redact_secrets,
            task_outcome=outcome,
        )
        summary = import_agent_run(request)
        emit_json(summary)


def _agent_artifacts(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[AgentArtifactInput, ...]:
    return tuple(AgentArtifactInput(role=role, path=path) for path in paths or ())


def register(app: typer.Typer) -> None:
    app.command(
        "import-run",
        help="Import an external agent run log as evidence.",
    )(import_run)
