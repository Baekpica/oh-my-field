from oh_my_field.domain.portability import (
    TargetStatusEntry,
    aggregate_target_validation_status,
    build_portability_health,
    normalize_target_validation_status,
)


def test_portability_health_keeps_export_import_and_validation_separate() -> None:
    exported_only = build_portability_health(export_count=1, targets=())

    assert exported_only.export_status == "exported"
    assert exported_only.import_status == "not_imported"
    assert exported_only.validation_status == "not_run"


def test_imported_target_still_needs_actual_validation() -> None:
    health = build_portability_health(
        export_count=0,
        targets=(
            TargetStatusEntry(
                target="hermes:qwen3.6-27b",
                validation_status="needs_validation",
            ),
        ),
    )

    assert health.export_status == "not_exported"
    assert health.import_status == "imported"
    assert health.validation_status == "needs_validation"


def test_validated_target_marks_health_validated() -> None:
    health = build_portability_health(
        export_count=1,
        targets=(
            TargetStatusEntry(
                target="generic:small-local",
                validation_status="validated",
                eval_recorded=True,
            ),
        ),
    )

    assert health.validation_status == "validated"
    assert health.target_validation_count == 1


def test_aggregate_prioritizes_adaptation_before_validation() -> None:
    status = aggregate_target_validation_status(
        (
            TargetStatusEntry(target="codex:gpt-5.5", validation_status="validated"),
            TargetStatusEntry(
                target="hermes:qwen3.6-27b",
                validation_status="needs_adaptation",
            ),
        ),
    )

    assert status == "needs_adaptation"


def test_unknown_overlay_status_falls_back_to_needs_validation() -> None:
    assert normalize_target_validation_status("static_check_only") == "needs_validation"
