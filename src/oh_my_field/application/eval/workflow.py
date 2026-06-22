from datetime import UTC

from oh_my_field.application.eval_support import (
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
    state_manifest,
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
    CapabilityManifest,
    CommandExecution,
    EvalCheck,
    EvalChecklistItem,
    EvalExpectedCheck,
    EvalResult,
    EvalRubricScore,
    EvalSet,
)
from oh_my_field.storage import (
    load_eval_set,
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
    state = EvalState(
        request=request,
        dependencies=dependencies or default_dependencies(),
    )
    state.update(_load_manifest(state))
    state.update(_load_source_evidence(state))
    state.update(_load_replay(state))
    state.update(_load_eval_set(state))
    state.update(_execute_harness(state))
    state.update(_build_eval(state))
    state.update(_validate_eval(state))
    state.update(_write_eval(state))
    state.update(_summarize(state))
    return state_summary(state)


def _load_manifest(state: EvalState) -> EvalState:
    request = state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    if manifest.name != request.capability_name:
        raise CapabilityNameMismatchError(
            requested_name=request.capability_name,
            manifest_name=manifest.name,
        )
    return EvalState(
        manifest=manifest,
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


def _load_eval_set(state: EvalState) -> EvalState:
    request = state_request(state)
    if request.eval_set_name is None:
        return EvalState(eval_set=None)
    eval_set = load_eval_set(request.eval_set_name, request.eval_set_dir)
    return EvalState(eval_set=eval_set)


def _execute_harness(state: EvalState) -> EvalState:
    request = state_request(state)
    manifest = state_manifest(state)
    command_executions = tuple(
        _execute_command(command, request, manifest)
        for command in _harness_commands(request, state.get("eval_set"))
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
    eval_set = state.get("eval_set")
    if eval_set is not None:
        checks.extend(_eval_set_checks(eval_set, tuple(checks)))
    created_at = dependencies.clock().astimezone(UTC)
    failures = tuple(check.message for check in checks if check.status == "fail")
    result = EvalResult(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        source_evidence_id=source_evidence.id,
        replay_id=None if replay is None else replay.id,
        runtime_profile=request.runtime_profile,
        eval_set_name=None if eval_set is None else eval_set.name,
        eval_case_ids=(
            () if eval_set is None else tuple(case.id for case in eval_set.cases)
        ),
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


def _execute_command(
    command: str,
    request: EvalRequest,
    manifest: CapabilityManifest,
) -> CommandExecution:
    try:
        return execute_shell_command(
            CommandExecutionRequest(
                command=command,
                cwd=request.command_cwd,
                timeout_seconds=request.command_timeout_seconds,
                approve_risk=request.approve_command_risk,
                allow_env=request.allow_env,
                approval_required_categories=(
                    manifest.workflow_control.approval_required_actions
                ),
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


def _harness_commands(
    request: EvalRequest,
    eval_set: EvalSet | None,
) -> tuple[str, ...]:
    if eval_set is None:
        return request.harness_commands
    case_commands = tuple(
        command for case in eval_set.cases for command in case.harness_commands
    )
    return (*request.harness_commands, *case_commands)


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


def _eval_set_checks(
    eval_set: EvalSet,
    observed_checks: tuple[EvalCheck, ...],
) -> tuple[EvalCheck, ...]:
    checks: list[EvalCheck] = [
        EvalCheck(
            name=f"eval_set_{eval_set.name}_loaded",
            status="pass",
            message=(f"loaded eval set {eval_set.name!r} version {eval_set.version!r}"),
        ),
    ]
    for case in eval_set.cases:
        checks.append(
            EvalCheck(
                name=f"eval_case_{case.id}_registered",
                status="pass",
                message=f"registered eval case {case.id!r}",
            ),
        )
        checks.extend(
            _eval_expected_check(
                case_id=case.id,
                expected=expected,
                observed_checks=observed_checks,
            )
            for expected in case.expected_checks
        )
    return tuple(checks)


def _eval_expected_check(
    *,
    case_id: str,
    expected: EvalExpectedCheck,
    observed_checks: tuple[EvalCheck, ...],
) -> EvalCheck:
    matched = _expected_check_observed(expected.name, observed_checks)
    if matched:
        return EvalCheck(
            name=f"eval_case_{case_id}_{_check_name(expected.name)}",
            status="pass",
            message=f"eval case {case_id!r} observed check {expected.name!r}",
        )
    if expected.flaky:
        return EvalCheck(
            name=f"eval_case_{case_id}_{_check_name(expected.name)}",
            status="pass",
            message=f"flaky eval check {expected.name!r} was not observed",
        )
    return EvalCheck(
        name=f"eval_case_{case_id}_{_check_name(expected.name)}",
        status="fail",
        message=f"eval case {case_id!r} missing expected check {expected.name!r}",
    )


def _expected_check_observed(
    expected_name: str,
    observed_checks: tuple[EvalCheck, ...],
) -> bool:
    needle = _check_name(expected_name)
    return any(
        needle in _check_name(check.name)
        or expected_name.casefold() in check.message.casefold()
        for check in observed_checks
    )


def _check_name(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_" for character in value.casefold()
    ).strip("_")
    return normalized or "item"


def _state_command_executions(
    state: EvalState,
) -> tuple[CommandExecution, ...]:
    command_executions = state.get("command_executions")
    if command_executions is None:
        return ()
    return command_executions
