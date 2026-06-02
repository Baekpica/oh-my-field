from datetime import UTC, datetime
from pathlib import Path

import pytest

from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    ReplayRecord,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import (
    DuplicateWriteError,
    EvidenceParseError,
    ManifestNotFoundError,
    ManifestParseError,
    load_evidence,
    load_manifest,
    load_replay,
    write_eval_result,
    write_evidence,
    write_manifest,
    write_replay,
)


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model=None),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="0" * 64,
            ),
        ),
        feedback=(),
        harness=HarnessResult(status="pass", checks=("schema_valid",), failures=()),
    )


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("load_evidence", "write_capability"),
        ),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid",),
            failures=(),
        ),
        runtime=RuntimeInfo(name="codex", model=None),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def make_replay_record() -> ReplayRecord:
    return ReplayRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        source_goal="triage repo issue",
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("load_evidence", "write_capability"),
        ),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid",),
            failures=(),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
    )


def make_eval_result() -> EvalResult:
    return EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        replay_id="20260602T010203Z-deadbeef",
        status="pass",
        checks=(EvalCheck(name="schema_valid", status="pass", message="ok"),),
        failures=(),
    )


def test_write_evidence_persists_json_and_refuses_duplicate(tmp_path: Path) -> None:
    record = make_evidence_record()

    evidence_path = write_evidence(record, tmp_path)
    loaded = load_evidence(record.id, tmp_path)

    assert evidence_path == tmp_path / f"{record.id}.json"
    assert loaded == record
    with pytest.raises(DuplicateWriteError):
        write_evidence(record, tmp_path)


def test_load_evidence_rejects_corrupt_json(tmp_path: Path) -> None:
    evidence_path = tmp_path / "bad.json"
    evidence_path.write_text("{", encoding="utf-8")

    with pytest.raises(EvidenceParseError):
        load_evidence("bad", tmp_path)


def test_load_manifest_reads_yaml_written_by_write_manifest(tmp_path: Path) -> None:
    manifest = make_manifest()

    manifest_path = write_manifest(manifest, tmp_path)
    loaded = load_manifest(manifest.name, tmp_path)

    assert manifest_path == tmp_path / manifest.name / "manifest.yaml"
    assert loaded == manifest


def test_load_manifest_rejects_missing_and_corrupt_yaml(tmp_path: Path) -> None:
    with pytest.raises(ManifestNotFoundError):
        load_manifest("missing_capability", tmp_path)

    corrupt_path = tmp_path / "repo_issue" / "manifest.yaml"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(ManifestParseError):
        load_manifest("repo_issue", tmp_path)


def test_write_replay_persists_json_and_refuses_duplicate(tmp_path: Path) -> None:
    record = make_replay_record()

    replay_path = write_replay(record, tmp_path)
    loaded = load_replay(record.id, tmp_path)

    assert replay_path == tmp_path / f"{record.id}.json"
    assert loaded == record
    with pytest.raises(DuplicateWriteError):
        write_replay(record, tmp_path)


def test_write_eval_result_persists_json_and_refuses_duplicate(
    tmp_path: Path,
) -> None:
    result = make_eval_result()

    eval_path = write_eval_result(result, tmp_path)
    expected_json = result.model_dump_json(indent=2) + "\n"

    assert eval_path.read_text(encoding="utf-8") == expected_json
    with pytest.raises(DuplicateWriteError):
        write_eval_result(result, tmp_path)
