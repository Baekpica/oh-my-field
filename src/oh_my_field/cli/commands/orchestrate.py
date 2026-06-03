from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.options import (
    capture_file_inputs,
    eval_checklist_items,
    eval_rubric_scores,
)
from oh_my_field.cli.output import emit_json
from oh_my_field.orchestrate import (
    OrchestrateError,
    OrchestrateRequest,
    ResumeRequest,
    load_workflow_summary,
    run_orchestrate_workflow,
    run_resume_workflow,
)
from oh_my_field.rollback import RollbackError, RollbackRequest, rollback_workflow


def run_pipeline(
    goal: Annotated[str, typer.Option("--goal")],
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
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
    harness_command: Annotated[
        list[str] | None,
        typer.Option("--harness-command"),
    ] = None,
    checklist_pass: Annotated[
        list[str] | None,
        typer.Option("--checklist-pass"),
    ] = None,
    checklist_fail: Annotated[
        list[str] | None,
        typer.Option("--checklist-fail"),
    ] = None,
    rubric_score: Annotated[
        list[str] | None,
        typer.Option("--rubric-score"),
    ] = None,
    runtime_tool: Annotated[
        list[str] | None,
        typer.Option("--runtime-tool"),
    ] = None,
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
    field: Annotated[str, typer.Option("--field")] = "local",
    runtime: Annotated[str, typer.Option("--runtime")] = "codex",
    model: Annotated[str | None, typer.Option("--model")] = None,
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    allow_failed_capture: Annotated[
        bool,
        typer.Option("--allow-failed-capture"),
    ] = False,
    skip_replay_execute: Annotated[
        bool,
        typer.Option("--skip-replay-execute"),
    ] = False,
    skip_optional_context: Annotated[
        bool,
        typer.Option("--skip-optional-context"),
    ] = False,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(
        ".omf/evals",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    request = OrchestrateRequest(
        goal=goal,
        capability_name=name,
        description=description,
        version=version,
        field=field,
        runtime=runtime,
        model=model,
        runtime_tools=tuple(runtime_tool or ()),
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
        harness_commands=tuple(harness_command or ()),
        checklist_items=eval_checklist_items(
            passes=checklist_pass,
            failures=checklist_fail,
        ),
        rubric_scores=eval_rubric_scores(rubric_score),
        execute_replay_commands=not skip_replay_execute,
        include_optional_context=not skip_optional_context,
        allow_failed_capture=allow_failed_capture,
        evidence_dir=evidence_dir,
        capabilities_dir=capabilities_dir,
        replay_dir=replay_dir,
        eval_dir=eval_dir,
        context_dir=context_dir,
        learning_dir=learning_dir,
        workflow_dir=workflow_dir,
    )
    with cli_errors(OrchestrateError):
        summary = run_orchestrate_workflow(request)
        emit_json(summary)


def resume(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    with cli_errors(OrchestrateError):
        summary = run_resume_workflow(
            ResumeRequest(run_id=run_id, workflow_dir=workflow_dir),
        )
        emit_json(summary)


def status(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    with cli_errors():
        summary = load_workflow_summary(run_id, workflow_dir)
        emit_json(summary)


def rollback(
    run_id: Annotated[str, typer.Argument()],
    to_node: Annotated[
        str,
        typer.Option(
            "--to-node",
            help=(
                "Pipeline node: import_evidence, promote_capability, "
                "pack_context, run_verification, evaluate_capability, or "
                "record_learning_patch."
            ),
        ),
    ],
    reason: Annotated[str, typer.Option("--reason")] = "manual rollback",
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    with cli_errors(RollbackError):
        summary = rollback_workflow(
            RollbackRequest(
                run_id=run_id,
                to_node=to_node,
                reason=reason,
                workflow_dir=workflow_dir,
            ),
        )
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "run",
        help="Process local OMF artifacts through the advanced pipeline.",
    )(run_pipeline)
    app.command("resume", help="Resume a pending workflow run.")(resume)
    app.command("status", help="Inspect workflow run status.")(status)
    app.command(
        "rollback",
        help="Move a workflow run back to an earlier node.",
    )(rollback)
