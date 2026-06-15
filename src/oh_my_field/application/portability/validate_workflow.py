import shlex
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from oh_my_field.application.portability.manifest_builder import (
    portability_from_overlay,
)
from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.application.portability.validation_support import (
    build_overlay,
    next_action_for_report,
    pass_rate_comparison,
    validated_status,
    validation_confidence,
    validation_report,
    write_failure_evidence,
    write_target_eval,
)
from oh_my_field.domain.models import CapabilityManifest, EvalCheck
from oh_my_field.domain.portability.models import (
    CapabilityValidationRequest,
    CapabilityValidationSummary,
    ContextRemapPlan,
    PortabilityTarget,
    TargetRunPlan,
    ValidationIssue,
    ValidationStatus,
)
from oh_my_field.infrastructure.fs.storage import (
    capability_package_paths,
    load_manifest,
)
from oh_my_field.infrastructure.portability.bundle_store import write_text
from oh_my_field.infrastructure.portability.overlay_store import (
    find_overlay,
    write_target_overlay,
)
from oh_my_field.infrastructure.portability.paths import target_slug
from oh_my_field.infrastructure.process.execution import (
    CommandExecutionRequest,
    assess_command_risk,
    execute_shell_command,
)


def validate_capability_package(
    request: CapabilityValidationRequest,
) -> CapabilityValidationSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    package_dir = capability_package_paths(
        request.capability_name,
        request.capabilities_dir,
    ).package_dir
    overlay = find_overlay(package_dir, runtime=request.target, model=request.model)
    target = overlay.target.model_copy(
        update={
            "model": request.model or overlay.target.model,
            "project": request.project or overlay.target.project,
        },
    )
    portability = portability_from_overlay(manifest, overlay, target)
    target_dir = package_dir / "imports" / target_slug(target)
    remap_plan = _load_remap_plan(target_dir)
    context_remapped = remap_plan is not None and not remap_plan.unresolved
    report = validation_report(
        manifest=manifest,
        portability=portability,
        available_tools=request.available_tools,
        context_remapped=context_remapped,
    )
    expected_artifacts = _expected_artifacts(request, manifest)
    run_plan, run_check, run_blockers = _run_target_hook(request, expected_artifacts)
    artifact_checks, artifact_blockers = _artifact_checks(
        expected_artifacts,
        request.command_cwd,
        enabled=run_plan.executed,
    )
    contract_check, contract_blockers = _contract_validator_check(
        request,
        package_dir,
        enabled=request.run_contract_validator and run_plan.executed,
    )
    extra_checks = tuple(
        check
        for check in (run_check, *artifact_checks, contract_check)
        if check is not None
    )
    runtime_blockers = (*run_blockers, *artifact_blockers, *contract_blockers)
    report = report.model_copy(
        update={
            "hard_blockers": (*report.hard_blockers, *runtime_blockers),
            "validation_confidence": validation_confidence(
                target_run_executed=run_plan.executed,
                target_run_passed=run_plan.executed and run_plan.exit_code == 0,
                expected_artifacts=expected_artifacts,
                artifact_checks=artifact_checks,
                contract_validator_executed=contract_check is not None,
                contract_validator_passed=(
                    contract_check is not None and contract_check.status == "pass"
                ),
            ),
        },
    )
    eval_result, eval_path = write_target_eval(
        report=report,
        manifest=manifest,
        eval_dir=request.eval_dir,
        extra_checks=extra_checks,
    )
    final_status = validated_status(
        report=report,
        eval_result=eval_result,
        run_executed=run_plan.executed,
    )
    report = report.model_copy(
        update={
            "status": final_status,
            "next_action": next_action_for_report(final_status, report.hard_blockers),
            "eval_id": eval_result.id,
            "eval_path": str(eval_path),
            "target_run": run_plan,
            "pass_rate_comparison": pass_rate_comparison(manifest, eval_result),
        },
    )
    if eval_result.status == "fail":
        evidence, evidence_path = write_failure_evidence(
            report=report,
            eval_result=eval_result,
            evidence_dir=request.evidence_dir,
        )
        report = report.model_copy(
            update={
                "failure_evidence_id": evidence.id,
                "failure_evidence_path": str(evidence_path),
            },
        )
    report_path = target_dir / "validation_report.yaml"
    write_text(report_path, yaml_dump(report), overwrite=True)
    overlay_path = write_target_overlay(
        target_dir=target_dir,
        overlay=build_overlay(report, portability, overrides=overlay.overrides),
        portability=portability,
        manifest=manifest,
        overwrite=True,
    )
    return CapabilityValidationSummary(
        capability_name=manifest.name,
        imported_package_path=str(package_dir),
        overlay_path=str(overlay_path),
        validation_report_path=str(report_path),
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_readiness_score=report.readiness.score,
        eval_id=report.eval_id,
        eval_path=report.eval_path,
        failure_evidence_id=report.failure_evidence_id,
        failure_evidence_path=report.failure_evidence_path,
        target_run_executed=run_plan.executed,
        target_run_exit_code=run_plan.exit_code,
        manual_run_required=run_plan.manual_run_required,
        next_commands=_next_commands(manifest.name, target, final_status),
    )


def _load_remap_plan(target_dir: Path) -> ContextRemapPlan | None:
    remap_path = target_dir / "context.remap.yaml"
    try:
        data = yaml.safe_load(remap_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    try:
        return ContextRemapPlan.model_validate(data)
    except ValidationError:
        return None


def _validation_run_command(request: CapabilityValidationRequest) -> str | None:
    if request.run_argv:
        return shlex.join(request.run_argv)
    return request.run_command


def _run_target_hook(
    request: CapabilityValidationRequest,
    expected_artifacts: tuple[str, ...],
) -> tuple[TargetRunPlan, EvalCheck | None, tuple[ValidationIssue, ...]]:
    command = _validation_run_command(request)
    if command is None:
        return (
            TargetRunPlan(
                manual_run_required=True,
                expected_artifacts=expected_artifacts,
            ),
            None,
            (),
        )
    risk = assess_command_risk(command)
    if risk.approval_required and not request.approve_command_risk:
        return (
            TargetRunPlan(
                target_run_command=command,
                manual_run_required=True,
                expected_artifacts=expected_artifacts,
                executed=False,
                approved=False,
                risk_categories=risk.categories,
            ),
            None,
            (),
        )
    execution = execute_shell_command(
        CommandExecutionRequest(
            command=command,
            cwd=request.command_cwd,
            timeout_seconds=request.command_timeout_seconds,
            approve_risk=request.approve_command_risk,
            allow_env=request.allow_env,
            argv=request.run_argv or None,
            require_cwd_inside_project=request.require_cwd_inside_project,
        ),
    )
    plan = TargetRunPlan(
        target_run_command=command,
        manual_run_required=False,
        expected_artifacts=expected_artifacts,
        executed=True,
        approved=execution.approved,
        exit_code=execution.exit_code,
        risk_categories=execution.risk_categories,
    )
    check = EvalCheck(
        name="target_run",
        status="pass" if execution.exit_code == 0 else "fail",
        message=f"target run exit code {execution.exit_code}",
    )
    blockers: tuple[ValidationIssue, ...] = ()
    if execution.exit_code != 0:
        blockers = (
            ValidationIssue(
                name="target_run_failed",
                message=f"target run exit code {execution.exit_code}",
                action="fix the target run failure and rerun validation",
            ),
        )
    return plan, check, blockers


def _artifact_checks(
    expected_artifacts: tuple[str, ...],
    cwd: Path,
    *,
    enabled: bool,
) -> tuple[tuple[EvalCheck, ...], tuple[ValidationIssue, ...]]:
    if not enabled or not expected_artifacts:
        return (), ()
    checks: list[EvalCheck] = []
    blockers: list[ValidationIssue] = []
    root = cwd.resolve()
    for artifact in expected_artifacts:
        artifact_path = Path(artifact)
        path = artifact_path if artifact_path.is_absolute() else root / artifact_path
        exists = path.exists()
        checks.append(
            EvalCheck(
                name=f"artifact_exists:{artifact}",
                status="pass" if exists else "fail",
                message=(
                    f"artifact exists: {artifact}"
                    if exists
                    else f"missing artifact: {artifact}"
                ),
            ),
        )
        if not exists:
            blockers.append(
                ValidationIssue(
                    name="missing_artifact",
                    message=f"missing artifact: {artifact}",
                    action="produce required artifacts and rerun validation",
                    path=artifact,
                ),
            )
    return tuple(checks), tuple(blockers)


def _contract_validator_check(
    request: CapabilityValidationRequest,
    package_dir: Path,
    *,
    enabled: bool,
) -> tuple[EvalCheck | None, tuple[ValidationIssue, ...]]:
    if not enabled:
        return None, ()
    validator = package_dir / "validators" / "validate_contract.py"
    if not validator.exists():
        return (
            EvalCheck(
                name="contract_validator",
                status="fail",
                message="contract validator missing",
            ),
            (
                ValidationIssue(
                    name="contract_validator_missing",
                    message="validators/validate_contract.py is missing",
                    action=(
                        "restore the contract validator or rerun without "
                        "--run-contract-validator"
                    ),
                    path="validators/validate_contract.py",
                ),
            ),
        )
    argv = (sys.executable, "validators/validate_contract.py")
    execution = execute_shell_command(
        CommandExecutionRequest(
            command=shlex.join(argv),
            cwd=package_dir,
            timeout_seconds=request.command_timeout_seconds,
            approve_risk=request.approve_command_risk,
            allow_env=request.allow_env,
            argv=argv,
            require_cwd_inside_project=False,
        ),
    )
    message = f"contract validator exit code {execution.exit_code}"
    check = EvalCheck(
        name="contract_validator",
        status="pass" if execution.exit_code == 0 else "fail",
        message=message,
    )
    if execution.exit_code == 0:
        return check, ()
    return (
        check,
        (
            ValidationIssue(
                name="contract_validator_failed",
                message=message,
                action="fix contract validation failures and rerun validation",
                path="validators/validate_contract.py",
            ),
        ),
    )


def _expected_artifacts(
    request: CapabilityValidationRequest,
    manifest: CapabilityManifest,
) -> tuple[str, ...]:
    if request.expected_artifacts:
        return request.expected_artifacts
    task_contract = manifest.task_contract
    if task_contract is not None and task_contract.expected_artifacts:
        return task_contract.expected_artifacts
    return tuple(
        contract.artifact_path
        for contract in manifest.artifact_contracts
        if contract.required
    )


def _target_flags(target: PortabilityTarget) -> str:
    flags = f"--target {target.runtime}"
    if target.model is not None:
        flags += f" --model {target.model}"
    return flags


def _next_commands(
    name: str,
    target: PortabilityTarget,
    status: ValidationStatus,
) -> tuple[str, ...]:
    flags = _target_flags(target)
    if status == "validated":
        return (f"omf registry {name}",)
    if status == "needs_validation":
        return (
            (
                f"omf capability validate {name} {flags} "
                "--run-command '<target-agent-run>'"
            ),
        )
    return (
        f"omf inspect import {name} {flags}",
        f"omf capability remap {name} {flags} --map source=target",
        (f"omf capability validate {name} {flags} --run-command '<target-agent-run>'"),
    )
