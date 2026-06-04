import shlex
from pathlib import Path

import yaml
from pydantic import ValidationError

from oh_my_field.application.portability.manifest_builder import (
    portability_from_overlay,
)
from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.application.portability.validation_support import (
    build_overlay,
    pass_rate_comparison,
    validated_status,
    validation_report,
    write_failure_evidence,
    write_target_eval,
)
from oh_my_field.domain.models import EvalCheck
from oh_my_field.domain.portability.lifecycle import next_validation_action
from oh_my_field.domain.portability.models import (
    CapabilityValidationRequest,
    CapabilityValidationSummary,
    ContextRemapPlan,
    TargetRunPlan,
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
    run_plan, run_check = _run_target_hook(request)
    eval_result, eval_path = write_target_eval(
        report=report,
        manifest=manifest,
        eval_dir=request.eval_dir,
        extra_checks=(run_check,) if run_check is not None else (),
    )
    final_status = validated_status(
        report=report,
        eval_result=eval_result,
        run_executed=run_plan.executed,
    )
    report = report.model_copy(
        update={
            "status": final_status,
            "next_action": next_validation_action(final_status),
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
) -> tuple[TargetRunPlan, EvalCheck | None]:
    command = _validation_run_command(request)
    if command is None:
        return (
            TargetRunPlan(
                manual_run_required=True,
                expected_artifacts=request.expected_artifacts,
            ),
            None,
        )
    risk = assess_command_risk(command)
    if risk.approval_required and not request.approve_command_risk:
        return (
            TargetRunPlan(
                target_run_command=command,
                manual_run_required=True,
                expected_artifacts=request.expected_artifacts,
                executed=False,
                approved=False,
                risk_categories=risk.categories,
            ),
            None,
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
        expected_artifacts=request.expected_artifacts,
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
    return plan, check
