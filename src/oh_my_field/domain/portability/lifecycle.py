from oh_my_field.domain.models import (
    PortabilityHealth,
    TargetStatusEntry,
    TargetValidationStatus,
)

_KNOWN_TARGET_VALIDATION_STATUSES: tuple[TargetValidationStatus, ...] = (
    "not_run",
    "needs_validation",
    "needs_adaptation",
    "validated",
)


def normalize_target_validation_status(status: object) -> TargetValidationStatus:
    if status in _KNOWN_TARGET_VALIDATION_STATUSES:
        return status
    return "needs_validation"


def build_portability_health(
    *,
    export_count: int,
    targets: tuple[TargetStatusEntry, ...],
) -> PortabilityHealth:
    return PortabilityHealth(
        export_status="exported" if export_count else "not_exported",
        import_status="imported" if targets else "not_imported",
        validation_status=aggregate_target_validation_status(targets),
        export_count=export_count,
        import_count=len(targets),
        target_validation_count=sum(1 for target in targets if target.eval_recorded),
        target_statuses=targets,
    )


def aggregate_target_validation_status(
    targets: tuple[TargetStatusEntry, ...],
) -> TargetValidationStatus:
    if not targets:
        return "not_run"
    statuses = {target.validation_status for target in targets}
    if "needs_adaptation" in statuses:
        return "needs_adaptation"
    if "needs_validation" in statuses:
        return "needs_validation"
    if statuses == {"validated"}:
        return "validated"
    return "needs_validation"
