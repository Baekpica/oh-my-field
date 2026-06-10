from datetime import UTC, datetime

from oh_my_field.models import (
    ArtifactContract,
    ArtifactSnapshot,
    EvidenceRecord,
    HarnessResult,
    RecordQuality,
    RunObservation,
    RuntimeInfo,
    TaskContract,
    ValidationCheckResult,
)


def test_evidence_record_accepts_hardened_record_contracts() -> None:
    evidence = EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="generate finance portfolio artifacts",
        field="runtime_case",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        final_artifacts=("output/report.json",),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        run_observations=(
            RunObservation(
                kind="input",
                summary="loaded portfolio fixture",
                path="inputs/portfolio.json",
            ),
        ),
        artifact_snapshots=(
            ArtifactSnapshot(
                path="output/report.json",
                role="final",
                kind="json",
                sha256="0" * 64,
                size_bytes=42,
                metadata={"valid_json": True},
            ),
        ),
        artifact_contracts=(
            ArtifactContract(
                name="report_json",
                artifact_path="output/report.json",
                artifact_kind="json",
                role="final",
                required=True,
                validation_checks=("artifact_exists:output/report.json",),
            ),
        ),
        validation_results=(
            ValidationCheckResult(
                name="artifact_exists:output/report.json",
                status="pass",
                message="artifact exists",
                artifact_path="output/report.json",
            ),
        ),
        task_contract=TaskContract(
            goal="generate finance portfolio artifacts",
            required_inputs=("inputs/portfolio.json",),
            expected_artifacts=("output/report.json",),
            validation_checks=("artifact_exists:output/report.json",),
        ),
        record_quality=RecordQuality(
            score=1.0,
            warnings=(),
            missing_sections=(),
            strict_ready=True,
        ),
    )

    dumped = evidence.model_dump(mode="json")

    assert dumped["artifact_snapshots"][0]["kind"] == "json"
    assert dumped["artifact_contracts"][0]["required"] is True
    assert dumped["validation_results"][0]["status"] == "pass"
    assert dumped["task_contract"]["mock_outputs_allowed"] is False
    assert dumped["record_quality"]["strict_ready"] is True
