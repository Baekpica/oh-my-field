from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from pydantic import ValidationError

from oh_my_field.adapters import (
    AdapterError,
    AgentArtifactInput,
    AgentImportRequest,
    import_agent_run,
)
from oh_my_field.capture import (
    CaptureError,
    CaptureFileInput,
    CaptureRequest,
    run_capture_workflow,
)
from oh_my_field.context import ContextError, ContextRequest, run_context_workflow
from oh_my_field.dashboard import (
    DEFAULT_DASHBOARD_PORT,
    DashboardError,
    DashboardPaths,
    DashboardServeRequest,
    build_dashboard_snapshot,
    create_dashboard_server,
)
from oh_my_field.eval import EvalError, EvalRequest, run_eval_workflow
from oh_my_field.eval_set import (
    EvalSetError,
    RegressionCaseRequest,
    upsert_regression_case,
)
from oh_my_field.export import ExportError, ExportRequest, run_export_workflow
from oh_my_field.health import (
    CapabilityHealthRequest,
    HealthError,
    run_card_workflow,
    run_harden_workflow,
    run_health_workflow,
)
from oh_my_field.inspection import InspectRequest, inspect_artifact
from oh_my_field.learn import LearnError, LearnRequest, run_learn_workflow
from oh_my_field.learning_patch import (
    LearningPatchError,
    LearningPatchRequest,
    apply_learning_patch,
)
from oh_my_field.models import (
    CapturedFileRole,
    EvalChecklistItem,
    EvalRubricScore,
    HumanReviewAction,
    PatchDecisionStatus,
    ReviewTargetType,
    StrictModel,
)
from oh_my_field.orchestrate import (
    OrchestrateError,
    OrchestrateRequest,
    ResumeRequest,
    load_workflow_summary,
    run_orchestrate_workflow,
    run_resume_workflow,
)
from oh_my_field.portability import (
    CapabilityPortabilityExportRequest,
    CapabilityPortabilityImportRequest,
    PortabilityError,
    export_capability_package,
    import_capability_package,
)
from oh_my_field.promote import PromoteError, PromoteRequest, run_promote_workflow
from oh_my_field.reflect import ReflectError, ReflectRequest, run_reflect_workflow
from oh_my_field.registry import RegistryError, RegistryRequest, run_registry_workflow
from oh_my_field.replay import ReplayError, ReplayRequest, run_replay_workflow
from oh_my_field.review import ReviewError, ReviewRequest, run_review_workflow
from oh_my_field.rollback import RollbackError, RollbackRequest, rollback_workflow
from oh_my_field.storage import StorageError
from oh_my_field.verify import VerifyError, VerifyRequest, verify_artifact

app = typer.Typer(
    help="oh-my-field turns tacit know-how into reusable capabilities.",
    no_args_is_help=True,
)
capability_app = typer.Typer(
    help="Export and import portable capability packages.",
    no_args_is_help=True,
)
app.add_typer(capability_app, name="capability")
RUBRIC_SCORE_REQUIRED_PARTS = 4
RUBRIC_SCORE_SPLIT_MAX = 4


class RubricScoreParseError(ValueError):
    def __str__(self) -> str:
        return "rubric score must use name:score:max_score:pass_threshold[:message]"


class EvalMatrixItem(StrictModel):
    runtime_profile: str
    eval_id: str
    eval_path: str
    status: str


class EvalMatrixSummary(StrictModel):
    capability_name: str
    results: tuple[EvalMatrixItem, ...]


class ReplayMatrixItem(StrictModel):
    runtime_profile: str
    replay_id: str
    replay_path: str
    harness_status: str


class ReplayMatrixSummary(StrictModel):
    capability_name: str
    results: tuple[ReplayMatrixItem, ...]


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
            *_capture_file_inputs("prompt", prompt),
            *_capture_file_inputs("context", context),
            *_capture_file_inputs("tool_call", tool_call),
            *_capture_file_inputs("command_output", command_output),
            *_capture_file_inputs("diff", diff),
            *_capture_file_inputs("test_result", test_result),
            *_capture_file_inputs("artifact", artifact),
        ),
        commands=tuple(command or ()),
        command_cwd=command_cwd,
        command_timeout_seconds=command_timeout_seconds,
        approve_command_risk=approve_command_risk,
        retries=retries,
        feedback=tuple(feedback or ()),
        user_interventions=tuple(user_intervention or ()),
        final_artifacts=tuple(final_artifact or ()),
        improvement_notes=tuple(improvement_note or ()),
        success_or_failure_label=outcome,
    )
    try:
        summary = run_capture_workflow(request)
    except (CaptureError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _capture_file_inputs(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[CaptureFileInput, ...]:
    return tuple(CaptureFileInput(role=role, path=path) for path in paths or ())


app.command("capture", help="Capture files, commands, and feedback as evidence.")(
    _capture,
)


def _promote(
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
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = run_promote_workflow(
            PromoteRequest(
                evidence_id=evidence_id,
                from_evidence_set=from_evidence_set,
                name=name,
                description=description,
                version=version,
                evidence_dir=evidence_dir,
                eval_dir=eval_dir,
                capabilities_dir=capabilities_dir,
            ),
        )
    except (PromoteError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("promote", help="Promote evidence or an evidence set into a capability.")(
    _promote,
)


def _health(
    capability_name: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    try:
        summary = run_health_workflow(
            CapabilityHealthRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                eval_dir=eval_dir,
            ),
        )
    except (HealthError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("health", help="Summarize capability health and next action.")(_health)


def _harden(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    try:
        summary = run_harden_workflow(
            CapabilityHealthRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                eval_dir=eval_dir,
            ),
        )
    except (HealthError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("harden", help="Recommend the next hardening actions for a capability.")(
    _harden,
)


def _card(
    capability_name: Annotated[str, typer.Argument()],
    write: Annotated[bool, typer.Option("--write")] = False,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = run_card_workflow(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            write=write,
        )
    except (HealthError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("card", help="Read or rewrite a capability card.")(_card)


def _capability_export(
    capability_name: Annotated[str, typer.Argument()],
    target: Annotated[
        Literal["codex", "claude_code", "hermes", "generic"],
        typer.Option("--target"),
    ],
    out: Annotated[Path, typer.Option("--out")],
    target_model: Annotated[str | None, typer.Option("--target-model")] = None,
    target_project: Annotated[str | None, typer.Option("--target-project")] = None,
    source_project: Annotated[str | None, typer.Option("--source-project")] = None,
    source_reasoning_effort: Annotated[
        str | None,
        typer.Option("--source-reasoning-effort"),
    ] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = export_capability_package(
            CapabilityPortabilityExportRequest(
                capability_name=capability_name,
                target=target,
                target_model=target_model,
                target_project=target_project,
                source_project=source_project,
                source_reasoning_effort=source_reasoning_effort,
                out=out,
                capabilities_dir=capabilities_dir,
            ),
        )
    except (PortabilityError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


capability_app.command(
    "export",
    help="Export a capability package for a target runtime/model.",
)(_capability_export)


def _capability_import(
    bundle_path: Annotated[Path, typer.Argument()],
    runtime: Annotated[
        Literal["codex", "claude_code", "hermes", "generic"] | None,
        typer.Option("--runtime"),
    ] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    project: Annotated[str | None, typer.Option("--project")] = None,
    validate: Annotated[bool, typer.Option("--validate")] = False,
    available_tool: Annotated[
        list[str] | None,
        typer.Option("--available-tool"),
    ] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = import_capability_package(
            CapabilityPortabilityImportRequest(
                bundle_path=bundle_path,
                runtime=runtime,
                model=model,
                project=project,
                validate_import=validate,
                available_tools=tuple(available_tool or ()),
                capabilities_dir=capabilities_dir,
            ),
        )
    except (PortabilityError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


capability_app.command(
    "import",
    help="Import a portable capability package and write a target validation report.",
)(_capability_import)


def _replay(
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
    matrix: Annotated[list[str] | None, typer.Option("--matrix")] = None,
) -> None:
    try:
        request = ReplayRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            execute_commands=execute,
            command_cwd=command_cwd,
            command_timeout_seconds=command_timeout_seconds,
            approve_command_risk=approve_command_risk,
        )
        profiles = _matrix_profiles(matrix)
        if profiles:
            results = tuple(
                _replay_matrix_item(request, profile) for profile in profiles
            )
            typer.echo(
                ReplayMatrixSummary(
                    capability_name=capability_name,
                    results=results,
                ).model_dump_json(),
            )
            return
        summary = run_replay_workflow(
            request,
        )
    except (ReplayError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("replay", help="Replay a capability against its source evidence.")(
    _replay,
)


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


def _eval(
    capability_name: Annotated[str, typer.Argument()],
    replay_id: Annotated[str | None, typer.Option("--replay-id")] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(
        ".omf/evals",
    ),
    eval_set: Annotated[str | None, typer.Option("--eval-set")] = None,
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
    matrix: Annotated[list[str] | None, typer.Option("--matrix")] = None,
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
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 60,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
) -> None:
    try:
        request = EvalRequest(
            capability_name=capability_name,
            replay_id=replay_id,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            eval_dir=eval_dir,
            eval_set_dir=eval_set_dir,
            eval_set_name=eval_set,
            harness_commands=tuple(harness_command or ()),
            checklist_items=_eval_checklist_items(
                passes=checklist_pass,
                failures=checklist_fail,
            ),
            rubric_scores=_eval_rubric_scores(rubric_score),
            command_cwd=command_cwd,
            command_timeout_seconds=command_timeout_seconds,
            approve_command_risk=approve_command_risk,
        )
        profiles = _matrix_profiles(matrix)
        if profiles:
            results = tuple(
                _eval_matrix_item(request, profile) for profile in profiles
            )
            typer.echo(
                EvalMatrixSummary(
                    capability_name=capability_name,
                    results=results,
                ).model_dump_json(),
            )
            return
        summary = run_eval_workflow(request)
    except (EvalError, StorageError, ValidationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("eval", help="Evaluate a capability with harness, rubric, or matrix runs.")(
    _eval,
)


def _matrix_profiles(values: list[str] | None) -> tuple[str, ...]:
    profiles = [
        profile.strip()
        for value in values or ()
        for profile in value.split(",")
        if profile.strip()
    ]
    return tuple(dict.fromkeys(profiles))


def _eval_matrix_item(request: EvalRequest, runtime_profile: str) -> EvalMatrixItem:
    summary = run_eval_workflow(
        request.model_copy(update={"runtime_profile": runtime_profile}),
    )
    return EvalMatrixItem(
        runtime_profile=runtime_profile,
        eval_id=summary.eval_id,
        eval_path=summary.eval_path,
        status=summary.status,
    )


def _regression_case(
    capability_name: Annotated[str, typer.Argument()],
    case_id: Annotated[str, typer.Option("--case-id")],
    eval_set: Annotated[str | None, typer.Option("--eval-set")] = None,
    eval_set_version: Annotated[str, typer.Option("--eval-set-version")] = "0.1.0",
    input_value: Annotated[list[str] | None, typer.Option("--input")] = None,
    check: Annotated[list[str] | None, typer.Option("--check")] = None,
    flaky_check: Annotated[list[str] | None, typer.Option("--flaky-check")] = None,
    harness_command: Annotated[
        list[str] | None,
        typer.Option("--harness-command"),
    ] = None,
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
) -> None:
    try:
        summary = upsert_regression_case(
            RegressionCaseRequest(
                capability_name=capability_name,
                eval_set_name=eval_set or f"{capability_name}_regression",
                eval_set_version=eval_set_version,
                case_id=case_id,
                inputs=tuple(input_value or ()),
                expected_checks=tuple(check or ()),
                flaky_checks=tuple(flaky_check or ()),
                harness_commands=tuple(harness_command or ()),
                eval_set_dir=eval_set_dir,
            ),
        )
    except (EvalSetError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("regression-case", help="Create or update a regression eval case.")(
    _regression_case,
)


def _eval_checklist_items(
    *,
    passes: list[str] | None,
    failures: list[str] | None,
) -> tuple[EvalChecklistItem, ...]:
    return (
        *(
            EvalChecklistItem(
                name=item,
                status="pass",
                message=f"checklist item passed: {item}",
            )
            for item in passes or ()
        ),
        *(
            EvalChecklistItem(
                name=item,
                status="fail",
                message=f"checklist item failed: {item}",
            )
            for item in failures or ()
        ),
    )


def _eval_rubric_scores(values: list[str] | None) -> tuple[EvalRubricScore, ...]:
    return tuple(_eval_rubric_score(value) for value in values or ())


def _eval_rubric_score(value: str) -> EvalRubricScore:
    parts = value.split(":", RUBRIC_SCORE_SPLIT_MAX)
    if len(parts) < RUBRIC_SCORE_REQUIRED_PARTS:
        raise RubricScoreParseError
    name, score_text, max_score_text, threshold_text, *message = parts
    score = float(score_text)
    max_score = float(max_score_text)
    pass_threshold = float(threshold_text)
    status = "pass" if score >= pass_threshold else "fail"
    default_message = f"rubric score {score:g}/{max_score:g}"
    return EvalRubricScore(
        name=name,
        score=score,
        max_score=max_score,
        pass_threshold=pass_threshold,
        status=status,
        message=message[0] if message else default_message,
    )


def _approve(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="approve",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=None,
        review_dir=review_dir,
    )


app.command("approve", help="Approve an evidence, capability, replay, or eval target.")(
    _approve,
)


def _reject(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="reject",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=None,
        review_dir=review_dir,
    )


app.command("reject", help="Reject an evidence, capability, replay, or eval target.")(
    _reject,
)


def _revise(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    revision: Annotated[str, typer.Option("--revision")],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="revise",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=revision,
        review_dir=review_dir,
    )


app.command("revise", help="Request revision for a reviewed artifact.")(_revise)


def _run_review_command(
    *,
    target_type: ReviewTargetType,
    target_id: str,
    action: HumanReviewAction,
    reviewer: str | None,
    notes: tuple[str, ...],
    revision_request: str | None,
    review_dir: Path,
    added_context: tuple[str, ...] = (),
    changed_goal: str | None = None,
    changed_constraint: str | None = None,
    regression_case: str | None = None,
) -> None:
    try:
        summary = run_review_workflow(
            ReviewRequest(
                target_type=target_type,
                target_id=target_id,
                action=action,
                reviewer=reviewer,
                notes=notes,
                revision_request=revision_request,
                added_context=added_context,
                changed_goal=changed_goal,
                changed_constraint=changed_constraint,
                regression_case=regression_case,
                review_dir=review_dir,
            ),
        )
    except (ReviewError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _review(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    action: Annotated[
        Literal[
            "approve",
            "reject",
            "revise",
            "add_context",
            "change_goal",
            "change_constraint",
            "mark_reusable",
            "mark_unsafe",
            "create_regression_case",
        ],
        typer.Argument(),
    ],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    revision: Annotated[str | None, typer.Option("--revision")] = None,
    added_context: Annotated[
        list[str] | None,
        typer.Option("--added-context"),
    ] = None,
    changed_goal: Annotated[str | None, typer.Option("--changed-goal")] = None,
    changed_constraint: Annotated[
        str | None,
        typer.Option("--changed-constraint"),
    ] = None,
    regression_case: Annotated[
        str | None,
        typer.Option("--regression-case"),
    ] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action=action,
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=revision,
        review_dir=review_dir,
        added_context=tuple(added_context or ()),
        changed_goal=changed_goal,
        changed_constraint=changed_constraint,
        regression_case=regression_case,
    )


app.command("review", help="Record a structured human review action.")(_review)


def _learn(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
) -> None:
    try:
        summary = run_learn_workflow(
            LearnRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                learning_dir=learning_dir,
            ),
        )
    except (LearnError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("learn", help="Export learning assets from capability evidence.")(_learn)


def _import_run(
    adapter: Annotated[
        Literal["codex", "claude_code", "hermes"],
        typer.Argument(),
    ],
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
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    try:
        summary = import_agent_run(
            AgentImportRequest(
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
            ),
        )
    except (AdapterError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _agent_artifacts(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[AgentArtifactInput, ...]:
    return tuple(AgentArtifactInput(role=role, path=path) for path in paths or ())


app.command("import-run", help="Import an external agent run log as evidence.")(
    _import_run,
)


def _verify(
    target_type: Annotated[
        Literal[
            "evidence",
            "capability",
            "replay",
            "eval",
            "context",
            "learning",
            "learning_patch",
            "reflection",
            "review",
            "export",
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
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(".omf/context"),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(".omf/reviews"),
    export_dir: Annotated[Path, typer.Option("--export-dir")] = Path(".omf/exports"),
) -> None:
    try:
        result = verify_artifact(
            VerifyRequest(
                target_type=target_type,
                target_id=target_id,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                replay_dir=replay_dir,
                eval_dir=eval_dir,
                context_dir=context_dir,
                learning_dir=learning_dir,
                learning_patch_dir=learning_patch_dir,
                reflection_dir=reflection_dir,
                review_dir=review_dir,
                export_dir=export_dir,
            ),
        )
    except (VerifyError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(result.model_dump_json())
    if result.status == "fail":
        raise typer.Exit(code=1)


app.command("verify", help="Verify artifact integrity chain hashes.")(_verify)


def _learn_patch(
    capability_name: Annotated[str, typer.Argument()],
    learning_id: Annotated[str, typer.Option("--learning-id")],
    patch_index: Annotated[int, typer.Option("--patch-index")],
    decision: Annotated[
        Literal["accept", "reject", "accepted", "rejected"],
        typer.Option("--decision"),
    ],
    patch_kind: Annotated[
        Literal["prompt", "context", "harness"],
        typer.Option("--patch-kind"),
    ] = "prompt",
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    before_eval_id: Annotated[
        str | None,
        typer.Option("--before-eval-id"),
    ] = None,
    after_eval_id: Annotated[str | None, typer.Option("--after-eval-id")] = None,
    pass_rate_delta: Annotated[
        float | None,
        typer.Option("--pass-rate-delta"),
    ] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
) -> None:
    try:
        summary = apply_learning_patch(
            LearningPatchRequest(
                capability_name=capability_name,
                learning_id=learning_id,
                patch_kind=patch_kind,
                patch_index=patch_index,
                decision=_patch_decision(decision),
                reviewer=reviewer,
                notes=tuple(note or ()),
                before_eval_id=before_eval_id,
                after_eval_id=after_eval_id,
                pass_rate_delta=pass_rate_delta,
                capabilities_dir=capabilities_dir,
                learning_dir=learning_dir,
                learning_patch_dir=learning_patch_dir,
            ),
        )
    except (LearningPatchError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _patch_decision(
    decision: Literal["accept", "reject", "accepted", "rejected"],
) -> PatchDecisionStatus:
    if decision in {"accept", "accepted"}:
        return "accepted"
    return "rejected"


app.command("learn-patch", help="Accept or reject a learning prompt patch.")(
    _learn_patch,
)


def _context(
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
    try:
        summary = run_context_workflow(
            ContextRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                context_dir=context_dir,
                include_optional=include_optional,
                query=query,
                max_chars=max_chars,
            ),
        )
    except (ContextError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("context", help="Build a context bundle from capability policy.")(_context)


def _run(
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
            *_capture_file_inputs("prompt", prompt),
            *_capture_file_inputs("context", context),
            *_capture_file_inputs("tool_call", tool_call),
            *_capture_file_inputs("command_output", command_output),
            *_capture_file_inputs("diff", diff),
            *_capture_file_inputs("test_result", test_result),
            *_capture_file_inputs("artifact", artifact),
        ),
        commands=tuple(command or ()),
        command_cwd=command_cwd,
        command_timeout_seconds=command_timeout_seconds,
        approve_command_risk=approve_command_risk,
        harness_commands=tuple(harness_command or ()),
        checklist_items=_eval_checklist_items(
            passes=checklist_pass,
            failures=checklist_fail,
        ),
        rubric_scores=_eval_rubric_scores(rubric_score),
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
    try:
        summary = run_orchestrate_workflow(request)
    except (OrchestrateError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("run", help="Run capture, promotion, context, replay, eval, and learn.")(
    _run,
)


def _resume(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = run_resume_workflow(
            ResumeRequest(run_id=run_id, workflow_dir=workflow_dir),
        )
    except (OrchestrateError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("resume", help="Resume a pending workflow run.")(_resume)


def _status(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = load_workflow_summary(run_id, workflow_dir)
    except StorageError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("status", help="Inspect workflow run status.")(_status)


def _dashboard(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = DEFAULT_DASHBOARD_PORT,
    once: Annotated[bool, typer.Option("--once")] = False,
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
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
) -> None:
    paths = DashboardPaths(
        capabilities_dir=capabilities_dir,
        evidence_dir=evidence_dir,
        replay_dir=replay_dir,
        eval_dir=eval_dir,
        workflow_dir=workflow_dir,
        review_dir=review_dir,
        eval_set_dir=eval_set_dir,
        learning_patch_dir=learning_patch_dir,
    )
    try:
        if once:
            typer.echo(build_dashboard_snapshot(paths).model_dump_json())
            return
        server = create_dashboard_server(
            DashboardServeRequest(host=host, port=port, paths=paths),
        )
    except (DashboardError, OSError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    address = cast("tuple[str, int]", server.server_address)
    typer.echo(f"Serving dashboard at http://{address[0]}:{address[1]}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return
    finally:
        server.server_close()


app.command("dashboard", help="Serve or print the local operating dashboard.")(
    _dashboard,
)


def _registry(
    capability_name: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    try:
        summary = run_registry_workflow(
            RegistryRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                eval_dir=eval_dir,
            ),
        )
    except (RegistryError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("registry", help="List capability registry health and metadata.")(_registry)


def _reflect(
    capability_name: Annotated[str, typer.Argument()],
    eval_id: Annotated[str | None, typer.Option("--eval-id")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
) -> None:
    try:
        summary = run_reflect_workflow(
            ReflectRequest(
                capability_name=capability_name,
                eval_id=eval_id,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                eval_dir=eval_dir,
                reflection_dir=reflection_dir,
                notes=tuple(note or ()),
            ),
        )
    except (ReflectError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("reflect", help="Generate a reflection report from evidence and evals.")(
    _reflect,
)


def _inspect(
    target_type: Annotated[
        Literal[
            "evidence",
            "capability",
            "replay",
            "eval",
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
) -> None:
    try:
        summary = inspect_artifact(
            InspectRequest(
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
            ),
        )
    except (StorageError, ValidationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("inspect", help="Inspect a stored oh-my-field artifact.")(_inspect)


def _export(
    capability_name: Annotated[str, typer.Argument()],
    approve_export: Annotated[
        bool,
        typer.Option("--approve-export"),
    ] = False,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    export_dir: Annotated[Path, typer.Option("--export-dir")] = Path(
        ".omf/exports",
    ),
) -> None:
    try:
        summary = run_export_workflow(
            ExportRequest(
                capability_name=capability_name,
                approve_export=approve_export,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                eval_dir=eval_dir,
                context_dir=context_dir,
                learning_dir=learning_dir,
                reflection_dir=reflection_dir,
                export_dir=export_dir,
            ),
        )
    except (ExportError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("export", help="Export a capability bundle after explicit approval.")(
    _export,
)


def _rollback(
    run_id: Annotated[str, typer.Argument()],
    to_node: Annotated[
        Literal[
            "observe_capture",
            "structure_promote",
            "context_pack",
            "execute_replay",
            "evaluate_harness",
            "learn_export",
        ],
        typer.Option("--to-node"),
    ],
    reason: Annotated[str, typer.Option("--reason")] = "manual rollback",
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = rollback_workflow(
            RollbackRequest(
                run_id=run_id,
                to_node=to_node,
                reason=reason,
                workflow_dir=workflow_dir,
            ),
        )
    except (RollbackError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("rollback", help="Move a workflow run back to an earlier node.")(_rollback)
