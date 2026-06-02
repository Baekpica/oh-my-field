from datetime import UTC

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from oh_my_field.eval_support import (
    CapabilityNameMismatchError,
    EvalDependencies,
    EvalError,
    EvalRequest,
    EvalState,
    EvalSummary,
    build_comparison_check,
    build_harness_check,
    default_dependencies,
    state_dependencies,
    state_manifest_source_evidence_id,
    state_request,
    state_result,
    state_result_path,
    state_source_evidence,
    state_summary,
)
from oh_my_field.execution import (
    CommandExecutionError,
    CommandExecutionRequest,
    execute_shell_command,
)
from oh_my_field.models import (
    CommandExecution,
    EvalCheck,
    EvalChecklistItem,
    EvalResult,
    EvalRubricScore,
)
from oh_my_field.storage import (
    load_evidence,
    load_manifest,
    load_replay,
    write_eval_result,
)

__all__ = ["EvalError", "EvalRequest", "run_eval_workflow"]


def run_eval_workflow(
    request: EvalRequest,
    dependencies: EvalDependencies | None = None,
) -> EvalSummary:
    graph = _build_eval_graph()
    initial_state = EvalState(
        request=request,
        dependencies=dependencies or default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return state_summary(final_state)


def _build_eval_graph() -> CompiledStateGraph[
    EvalState,
    None,
    EvalState,
    EvalState,
]:
    builder: StateGraph[EvalState, None, EvalState, EvalState] = StateGraph(EvalState)
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("load_replay", _load_replay)
    builder.add_node("execute_harness", _execute_harness)
    builder.add_node("build_eval", _build_eval)
    builder.add_node("validate_eval", _validate_eval)
    builder.add_node("write_eval", _write_eval)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "load_replay")
    builder.add_edge("load_replay", "execute_harness")
    builder.add_edge("execute_harness", "build_eval")
    builder.add_edge("build_eval", "validate_eval")
    builder.add_edge("validate_eval", "write_eval")
    builder.add_edge("write_eval", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _load_manifest(state: EvalState) -> EvalState:
    request = state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    if manifest.name != request.capability_name:
        raise CapabilityNameMismatchError(
            requested_name=request.capability_name,
            manifest_name=manifest.name,
        )
    return EvalState(
        manifest_source_evidence_id=manifest.source_evidence_id,
    )


def _load_source_evidence(state: EvalState) -> EvalState:
    request = state_request(state)
    source_evidence = load_evidence(
        state_manifest_source_evidence_id(state),
        request.evidence_dir,
    )
    return EvalState(source_evidence=source_evidence)


def _load_replay(state: EvalState) -> EvalState:
    request = state_request(state)
    if request.replay_id is None:
        return EvalState(replay=None)
    replay = load_replay(request.replay_id, request.replay_dir)
    return EvalState(replay=replay)


def _execute_harness(state: EvalState) -> EvalState:
    request = state_request(state)
    command_executions = tuple(
        _execute_command(command, request) for command in request.harness_commands
    )
    return EvalState(command_executions=command_executions)


def _build_eval(state: EvalState) -> EvalState:
    dependencies = state_dependencies(state)
    request = state_request(state)
    source_evidence = state_source_evidence(state)
    replay = state.get("replay")
    checks = [
        EvalCheck(
            name="manifest_loaded",
            status="pass",
            message=f"loaded manifest for capability {request.capability_name!r}",
        ),
        EvalCheck(
            name="source_evidence_loaded",
            status="pass",
            message=f"loaded source evidence {source_evidence.id!r}",
        ),
        build_harness_check(
            name="source_harness_pass",
            subject="source evidence",
            status=source_evidence.harness.status,
        ),
    ]
    if replay is not None:
        checks.extend(
            (
                EvalCheck(
                    name="replay_loaded",
                    status="pass",
                    message=f"loaded replay {replay.id!r}",
                ),
                build_comparison_check(
                    name="replay_matches_capability",
                    expected=request.capability_name,
                    actual=replay.capability_name,
                    label="capability",
                ),
                build_comparison_check(
                    name="replay_matches_source_evidence",
                    expected=source_evidence.id,
                    actual=replay.source_evidence_id,
                    label="source evidence",
                ),
                build_harness_check(
                    name="replay_harness_pass",
                    subject="replay",
                    status=replay.harness.status,
                ),
            ),
        )
    command_executions = _state_command_executions(state)
    checks.extend(_harness_command_checks(command_executions))
    checks.extend(_checklist_checks(request.checklist_items))
    checks.extend(_rubric_checks(request.rubric_scores))
    created_at = dependencies.clock().astimezone(UTC)
    failures = tuple(check.message for check in checks if check.status == "fail")
    result = EvalResult(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        source_evidence_id=source_evidence.id,
        replay_id=None if replay is None else replay.id,
        status="fail" if failures else "pass",
        checks=tuple(checks),
        failures=failures,
        command_executions=command_executions,
        checklist_items=request.checklist_items,
        rubric_scores=request.rubric_scores,
    )
    return EvalState(result=result)


def _validate_eval(state: EvalState) -> EvalState:
    result = state_result(state)
    checked = EvalResult.model_validate(result)
    return EvalState(result=checked)


def _write_eval(state: EvalState) -> EvalState:
    request = state_request(state)
    result = state_result(state)
    result_path = write_eval_result(result, request.eval_dir)
    return EvalState(result_path=result_path)


def _summarize(state: EvalState) -> EvalState:
    result = state_result(state)
    result_path = state_result_path(state)
    summary = EvalSummary(
        eval_id=result.id,
        eval_path=str(result_path),
        capability_name=result.capability_name,
        status=result.status,
    )
    return EvalState(summary=summary)


def _execute_command(command: str, request: EvalRequest) -> CommandExecution:
    try:
        return execute_shell_command(
            CommandExecutionRequest(
                command=command,
                cwd=request.command_cwd,
                timeout_seconds=request.command_timeout_seconds,
            ),
        )
    except CommandExecutionError as exc:
        return CommandExecution(
            command=command,
            cwd=str(request.command_cwd),
            exit_code=1,
            stderr=str(exc),
            duration_ms=0,
        )


def _harness_command_checks(
    command_executions: tuple[CommandExecution, ...],
) -> tuple[EvalCheck, ...]:
    return tuple(
        EvalCheck(
            name=f"harness_command_{index}",
            status="pass" if execution.exit_code == 0 else "fail",
            message=_harness_command_message(execution),
        )
        for index, execution in enumerate(command_executions, start=1)
    )


def _harness_command_message(execution: CommandExecution) -> str:
    if execution.exit_code == 0:
        return f"harness command passed: {execution.command!r}"
    detail = execution.stderr or execution.stdout or f"exit code {execution.exit_code}"
    return f"harness command failed: {execution.command!r}: {detail}"


def _checklist_checks(
    checklist_items: tuple[EvalChecklistItem, ...],
) -> tuple[EvalCheck, ...]:
    return tuple(
        EvalCheck(
            name=f"checklist_{index}_{_check_name(item.name)}",
            status=item.status,
            message=item.message,
        )
        for index, item in enumerate(checklist_items, start=1)
    )


def _rubric_checks(
    rubric_scores: tuple[EvalRubricScore, ...],
) -> tuple[EvalCheck, ...]:
    return tuple(
        EvalCheck(
            name=f"rubric_{index}_{_check_name(score.name)}",
            status=score.status,
            message=(
                f"{score.name}: {score.score:g}/{score.max_score:g} "
                f"(threshold {score.pass_threshold:g}) - {score.message}"
            ),
        )
        for index, score in enumerate(rubric_scores, start=1)
    )


def _check_name(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_"
        for character in value.casefold()
    ).strip("_")
    return normalized or "item"


def _state_command_executions(
    state: EvalState,
) -> tuple[CommandExecution, ...]:
    command_executions = state.get("command_executions")
    if command_executions is None:
        return ()
    return command_executions
