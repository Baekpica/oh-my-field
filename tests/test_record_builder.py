from datetime import UTC, datetime
from pathlib import Path

from oh_my_field.application.record_builder import harden_evidence_record
from oh_my_field.models import EvidenceRecord, HarnessResult, RuntimeInfo


def make_record(*, artifacts: tuple[str, ...]) -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="generate finance portfolio artifacts",
        field="runtime_case",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        input_context=("inputs/portfolio.json",),
        final_artifacts=artifacts,
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        task_outcome="success",
        success_or_failure_label="success",
    )


def test_harden_evidence_record_snapshots_artifacts_and_contracts(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "inputs" / "portfolio.json"
    output_path = tmp_path / "output" / "report.json"
    charts_dir = tmp_path / "output" / "charts"
    input_path.parent.mkdir(parents=True)
    output_path.parent.mkdir(parents=True)
    charts_dir.mkdir()
    input_path.write_text('{"cash": 100}', encoding="utf-8")
    output_path.write_text('{"total": 100}', encoding="utf-8")
    charts_dir.joinpath("allocation.csv").write_text(
        "asset,value\nCash,100\n",
        encoding="utf-8",
    )

    hardened = harden_evidence_record(
        make_record(artifacts=("output/report.json", "output/charts")),
        project_root=tmp_path,
    )

    assert [snapshot.path for snapshot in hardened.artifact_snapshots] == [
        "output/report.json",
        "output/charts",
    ]
    assert hardened.artifact_snapshots[0].kind == "json"
    assert hardened.artifact_snapshots[0].metadata["valid_json"] is True
    assert hardened.artifact_snapshots[1].kind == "directory"
    assert hardened.artifact_snapshots[1].directory_entries == ("allocation.csv",)
    assert [contract.artifact_path for contract in hardened.artifact_contracts] == [
        "output/report.json",
        "output/charts",
    ]
    assert hardened.task_contract is not None
    assert hardened.task_contract.required_inputs == ("inputs/portfolio.json",)
    assert hardened.task_contract.expected_artifacts == (
        "output/report.json",
        "output/charts",
    )
    assert all(result.status == "pass" for result in hardened.validation_results)
    assert hardened.record_quality is not None
    assert hardened.record_quality.strict_ready is True
    assert hardened.record_quality.missing_sections == ()


def test_harden_evidence_record_marks_missing_artifact_not_strict_ready(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "inputs" / "portfolio.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text('{"cash": 100}', encoding="utf-8")

    hardened = harden_evidence_record(
        make_record(artifacts=("output/missing.json",)),
        project_root=tmp_path,
    )

    assert hardened.validation_results[0].status == "fail"
    assert hardened.validation_results[0].name == "artifact_exists:output/missing.json"
    assert hardened.record_quality is not None
    assert hardened.record_quality.strict_ready is False
    assert "passing_validation" in hardened.record_quality.missing_sections
