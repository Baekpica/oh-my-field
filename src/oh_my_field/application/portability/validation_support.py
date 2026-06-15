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
    ConfidenceLevel,
    EvalPassRateComparison,
    PortabilityManifest,
    PortabilityReadiness,
    PortabilityRisk,
    RiskLevel,
    TargetOverlay,
    TargetOverrides,
    TargetValidationReport,
    ToolCompatibilityStatus,
    ValidationConfidence,
    ValidationConfidenceFactor,
    ValidationIssue,
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

LOW_RISK_THRESHOLD = 0.85
MEDIUM_RISK_THRESHOLD = 0.65
HIGH_RISK_THRESHOLD = 0.4
HIGH_CONFIDENCE_THRESHOLD = 0.8
MEDIUM_CONFIDENCE_THRESHOLD = 0.5


def validated_status(
    *,
    report: TargetValidationReport,
    eval_result: EvalResult,
    run_executed: bool,
) -> ValidationStatus:
    if report.hard_blockers or eval_result.status == "fail":
        return "needs_adaptation"
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
        hard_blockers=report.hard_blockers,
        warnings=report.warnings,
        portability_risk=report.portability_risk,
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
    hard_blockers = _static_hard_blockers(
        unavailable_tools=unavailable_tools,
        context_remap_needed=context_remap_needed,
    )
    warnings = _warnings(readiness)
    status: ValidationStatus = (
        "needs_adaptation" if hard_blockers else "needs_validation"
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
        hard_blockers=hard_blockers,
        warnings=warnings,
        portability_risk=portability_risk(readiness),
        validation_confidence=validation_confidence(
            target_run_executed=False,
            target_run_passed=False,
            expected_artifacts=(),
            artifact_checks=(),
            contract_validator_executed=False,
            contract_validator_passed=False,
        ),
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
        next_action=next_action_for_report(status, hard_blockers),
    )


def next_action_for_report(
    status: ValidationStatus,
    hard_blockers: tuple[ValidationIssue, ...],
) -> str:
    if hard_blockers:
        first = hard_blockers[0]
        if first.action is not None:
            return first.action
        return f"resolve {first.name} and rerun target validation"
    return next_validation_action(status)


def portability_risk(readiness: PortabilityReadiness) -> PortabilityRisk:
    return PortabilityRisk(
        score=readiness.score,
        level=_risk_level(readiness.score),
        advisory_only=True,
        factors=readiness.factors,
    )


def validation_confidence(  # noqa: PLR0913
    *,
    target_run_executed: bool,
    target_run_passed: bool,
    expected_artifacts: tuple[str, ...],
    artifact_checks: tuple[EvalCheck, ...],
    contract_validator_executed: bool,
    contract_validator_passed: bool,
) -> ValidationConfidence:
    score = 0.0
    factors = [
        ValidationConfidenceFactor(
            name="target_run_observed",
            observed=target_run_executed,
            message=(
                "target run executed"
                if target_run_executed
                else "target run has not executed"
            ),
        ),
        ValidationConfidenceFactor(
            name="target_run_exit_zero",
            observed=target_run_passed,
            message=(
                "target run exited 0"
                if target_run_passed
                else "target run did not pass or has not executed"
            ),
        ),
    ]
    if target_run_passed:
        score += 0.45

    if expected_artifacts:
        artifacts_present = bool(artifact_checks) and all(
            check.status == "pass" for check in artifact_checks
        )
        factors.append(
            ValidationConfidenceFactor(
                name="required_artifacts_present",
                observed=artifacts_present,
                message=(
                    "required artifacts are present"
                    if artifacts_present
                    else "required artifacts are missing or unchecked"
                ),
            ),
        )
        if artifacts_present:
            score += 0.3

    factors.append(
        ValidationConfidenceFactor(
            name="contract_validator_passed",
            observed=contract_validator_passed,
            message=(
                "contract validator passed"
                if contract_validator_passed
                else "contract validator not run or did not pass"
            ),
        ),
    )
    if contract_validator_executed and contract_validator_passed:
        score += 0.25

    score = min(1.0, round(score, 2))
    return ValidationConfidence(
        score=score,
        level=_confidence_level(score),
        advisory_only=True,
        factors=tuple(factors),
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
            status="pass",
            message=(
                f"portability readiness {report.readiness.score:.2f}; "
                "advisory only"
            ),
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
            required_checks=("tool_compatibility", "context_remap", "target_run"),
            human_review_required=True,
        ),
        success_or_failure_label="failure",
        improvement_notes=(
            "resolve target validation blockers and rerun target validation",
        ),
    )
    evidence = append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )
    return evidence, write_evidence(evidence, evidence_dir)


def _static_hard_blockers(
    *,
    unavailable_tools: tuple[str, ...],
    context_remap_needed: bool,
) -> tuple[ValidationIssue, ...]:
    blockers = [
        ValidationIssue(
            name=f"unavailable_tool:{tool}",
            message=f"required tool unavailable: {tool}",
            action="make the required tool available or adapt the target package",
        )
        for tool in unavailable_tools
    ]
    if context_remap_needed:
        blockers.append(
            ValidationIssue(
                name="unresolved_context_remap",
                message="project transfer requires a completed context remap",
                action=(
                    "run omf capability remap for the target project "
                    "and rerun validation"
                ),
            ),
        )
    return tuple(blockers)


def _warnings(readiness: PortabilityReadiness) -> tuple[ValidationIssue, ...]:
    return tuple(
        ValidationIssue(
            name=factor.name,
            message=f"{factor.reason}; advisory portability risk {factor.delta:+.2f}",
        )
        for factor in readiness.factors
    )


def _risk_level(score: float) -> RiskLevel:
    if score >= LOW_RISK_THRESHOLD:
        return "low"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    return "severe"


def _confidence_level(score: float) -> ConfidenceLevel:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


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
