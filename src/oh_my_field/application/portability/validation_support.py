from datetime import UTC, datetime
from pathlib import Path

from oh_my_field.application.portability.ids import new_id
from oh_my_field.domain.models import (
    CapabilityManifest,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
)
from oh_my_field.domain.portability.lifecycle import next_validation_action
from oh_my_field.domain.portability.models import (
    PORTABILITY_REQUIRED_PASS_RATE,
    EvalPassRateComparison,
    PortabilityManifest,
    TargetOverlay,
    TargetOverrides,
    TargetValidationReport,
    ToolCompatibilityStatus,
    ValidationStatus,
)
from oh_my_field.domain.portability.readiness import (
    context_remap_required as needs_context_remap,
)
from oh_my_field.domain.portability.readiness import (
    model_delta,
    model_downgrade,
    portability_readiness,
)
from oh_my_field.infrastructure.fs.storage import write_eval_result, write_evidence
from oh_my_field.infrastructure.portability.paths import runtime_profile
from oh_my_field.integrity import append_integrity_link


def validated_status(
    *,
    report: TargetValidationReport,
    eval_result: EvalResult,
    run_executed: bool,
) -> ValidationStatus:
    if (
        report.unavailable_tools
        or report.readiness.score < PORTABILITY_REQUIRED_PASS_RATE
    ):
        return "needs_adaptation"
    if eval_result.status == "fail":
        return "needs_adaptation"
    # Static target-side checks pass. Only an executed, passing target run
    # earns "validated"; otherwise the import still needs a real target run.
    return "validated" if run_executed else "needs_validation"


def build_overlay(
    report: TargetValidationReport,
    portability: PortabilityManifest,
    overrides: TargetOverrides | None = None,
) -> TargetOverlay:
    return TargetOverlay(
        capability_name=report.capability_name,
        source=report.source,
        target=report.target,
        direct_execution_allowed=portability.agent_view.direct_execution_allowed,
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_readiness_score=report.readiness.score,
        transfer_type=portability.adaptation.transfer_type,
        overrides=overrides
        or TargetOverrides(
            instruction_variant="compact" if model_downgrade(portability) else "base",
            context_variant=(
                "compressed"
                if portability.compatibility.compression_required
                else "full"
            ),
            required_human_review=portability.adaptation.human_review_required,
        ),
        eval_id=report.eval_id,
        failure_evidence_id=report.failure_evidence_id,
    )


def validation_report(
    *,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
    available_tools: tuple[str, ...],
    context_remapped: bool = False,
) -> TargetValidationReport:
    unavailable_tools = _unavailable_tools(
        required_tools=portability.compatibility.required_tools,
        available_tools=available_tools,
    )
    tool_compatibility = _tool_compatibility(
        available_tools=available_tools,
        unavailable_tools=unavailable_tools,
    )
    readiness = portability_readiness(
        portability=portability,
        unavailable_tools=unavailable_tools,
    )
    context_remap_needed = needs_context_remap(portability) and not context_remapped
    status: ValidationStatus = (
        "needs_adaptation"
        if unavailable_tools
        or readiness.score < portability.validation.required_pass_rate
        else "needs_validation"
    )
    return TargetValidationReport(
        capability_name=manifest.name,
        source=portability.source,
        target=portability.target,
        tool_compatibility=tool_compatibility,
        unavailable_tools=unavailable_tools,
        context_remap_required=context_remap_needed,
        eval_set=portability.validation.eval_set,
        initial_pass_rate=portability.validation.current_pass_rate,
        readiness=readiness,
        model_delta=model_delta(portability),
        compact_instruction_path=(
            "instructions/compact.md" if model_downgrade(portability) else None
        ),
        compressed_context_path=(
            "context/context.pack.md"
            if portability.compatibility.compression_required
            else None
        ),
        status=status,
        next_action=_next_action_with_launcher_warning(status, portability),
    )


def _next_action_with_launcher_warning(
    status: ValidationStatus,
    portability: PortabilityManifest,
) -> str:
    action = next_validation_action(status)
    if not portability.agent_view.direct_execution_allowed:
        return action
    return (
        "re-export with `--skill-style launcher` so the target agent enters "
        f"the OMF lifecycle instead of executing the skill directly; then {action}"
    )


def write_target_eval(
    *,
    report: TargetValidationReport,
    manifest: CapabilityManifest,
    eval_dir: Path,
    extra_checks: tuple[EvalCheck, ...] = (),
) -> tuple[EvalResult, Path]:
    created_at = datetime.now(UTC)
    checks = (
        EvalCheck(
            name="tool_compatibility",
            status="pass" if report.tool_compatibility != "partial" else "fail",
            message=f"tool compatibility: {report.tool_compatibility}",
        ),
        EvalCheck(
            name="context_remap",
            status="fail" if report.context_remap_required else "pass",
            message=(
                "context remap required"
                if report.context_remap_required
                else "context remap not required"
            ),
        ),
        EvalCheck(
            name="portability_readiness",
            status=(
                "pass"
                if report.readiness.score >= PORTABILITY_REQUIRED_PASS_RATE
                else "fail"
            ),
            message=f"portability readiness {report.readiness.score:.2f}",
        ),
        *extra_checks,
    )
    failures = tuple(check.message for check in checks if check.status == "fail")
    result = EvalResult(
        id=new_id(created_at),
        created_at=created_at,
        capability_name=manifest.name,
        source_evidence_id=manifest.source_evidence_id,
        runtime_profile=runtime_profile(report.target),
        eval_set_name=report.eval_set,
        status="fail" if failures else "pass",
        checks=checks,
        failures=failures,
    )
    result = append_integrity_link(result, artifact_type="eval", artifact_id=result.id)
    return result, write_eval_result(result, eval_dir)


def pass_rate_comparison(
    manifest: CapabilityManifest,
    eval_result: EvalResult,
) -> EvalPassRateComparison:
    source = (
        manifest.promotion_metrics.eval_pass_rate
        if manifest.promotion_metrics is not None
        else None
    )
    total = len(eval_result.checks)
    target = (
        sum(check.status == "pass" for check in eval_result.checks) / total
        if total
        else None
    )
    delta = (
        round(target - source, 2) if source is not None and target is not None else None
    )
    return EvalPassRateComparison(
        source_pass_rate=source,
        target_pass_rate=target,
        delta=delta,
    )


def write_failure_evidence(
    *,
    report: TargetValidationReport,
    eval_result: EvalResult,
    evidence_dir: Path,
) -> tuple[EvidenceRecord, Path]:
    created_at = datetime.now(UTC)
    evidence = EvidenceRecord(
        id=new_id(created_at),
        created_at=created_at,
        capability_id=report.capability_name,
        goal=f"portability validation for {report.capability_name}",
        normalized_goal=f"validate target portability for {report.capability_name}",
        field=report.target.project or "target_project",
        runtime=RuntimeInfo(name=report.target.runtime, model=report.target.model),
        errors=eval_result.failures,
        feedback=(
            f"portability readiness {report.readiness.score:.2f}",
            f"target eval {eval_result.id} failed",
        ),
        harness=HarnessResult(
            status="fail",
            checks=tuple(check.name for check in eval_result.checks),
            failures=eval_result.failures,
            required_checks=("tool_compatibility", "portability_readiness"),
            human_review_required=True,
        ),
        success_or_failure_label="failure",
        improvement_notes=(
            "adapt target runtime tools, context mapping, or compact instructions",
        ),
    )
    evidence = append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )
    return evidence, write_evidence(evidence, evidence_dir)


def _unavailable_tools(
    *,
    required_tools: tuple[str, ...],
    available_tools: tuple[str, ...],
) -> tuple[str, ...]:
    if not available_tools:
        return ()
    available = set(available_tools)
    return tuple(tool for tool in required_tools if tool not in available)


def _tool_compatibility(
    *,
    available_tools: tuple[str, ...],
    unavailable_tools: tuple[str, ...],
) -> ToolCompatibilityStatus:
    if not available_tools:
        return "unknown"
    if unavailable_tools:
        return "partial"
    return "pass"
