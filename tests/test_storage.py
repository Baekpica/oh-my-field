from datetime import UTC, datetime
from pathlib import Path

import pytest

from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    ContextBundle,
    ContextPolicy,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    HumanReview,
    HumanReviewRecord,
    LearningExport,
    PromotionCriteria,
    ReflectionReport,
    ReplayRecord,
    ReviewTargetType,
    RuntimeInfo,
    WorkflowManifest,
    WorkflowRunConfig,
    WorkflowRunRecord,
    WorkflowRunStatus,
)
from oh_my_field.storage import (
    DuplicateWriteError,
    EvidenceParseError,
    ManifestNotFoundError,
    ManifestParseError,
    list_eval_results,
    list_manifests,
    load_eval_result,
    load_evidence,
    load_manifest,
    load_replay,
    load_workflow_run,
    write_context_bundle,
    write_eval_result,
    write_evidence,
    write_human_review,
    write_learning_export,
    write_manifest,
    write_reflection_report,
    write_replay,
    write_workflow_run,
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


def make_human_review_record(
    target_type: ReviewTargetType = "capability",
) -> HumanReviewRecord:
    return HumanReviewRecord(
        id="20260602T010205Z-cafebabe",
        created_at=datetime(2026, 6, 2, 1, 2, 5, tzinfo=UTC),
        target_type=target_type,
        target_id="repo_issue",
        action="approve",
        review=HumanReview(
            status="approved",
            reviewer="operator",
            notes=("approved",),
            reviewed_at=datetime(2026, 6, 2, 1, 2, 5, tzinfo=UTC),
        ),
    )


def make_learning_export() -> LearningExport:
    return LearningExport(
        id="20260602T010206Z-baddcafe",
        created_at=datetime(2026, 6, 2, 1, 2, 6, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        prompt_improvement_candidates=("run tests",),
    )


def make_context_bundle() -> ContextBundle:
    return ContextBundle(
        id="20260602T010207Z-facefeed",
        created_at=datetime(2026, 6, 2, 1, 2, 7, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        required_context=(
            CapturedTextFile(
                role="context",
                path="repo.md",
                content="Repository constraints.",
                size_bytes=23,
                sha256="0" * 64,
            ),
        ),
        policy=ContextPolicy(required=("repo.md",)),
    )


def make_workflow_run(status: WorkflowRunStatus = "running") -> WorkflowRunRecord:
    return WorkflowRunRecord(
        id="20260602T010208Z-1234abcd",
        created_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        goal="triage repo issue",
        status=status,
        current_node=None if status == "completed" else "import_evidence",
        config=WorkflowRunConfig(
            capability_name="repo_issue",
            description="GitHub issue triage capability",
            version="0.1.0",
            field="local",
            runtime="codex",
            command_cwd=".",
            command_timeout_seconds=60,
            evidence_dir=".omf/evidence",
            capabilities_dir="capabilities",
            replay_dir=".omf/replays",
            eval_dir=".omf/evals",
            context_dir=".omf/context",
            learning_dir=".omf/learning",
        ),
    )


def make_reflection_report() -> ReflectionReport:
    return ReflectionReport(
        id="20260602T010209Z-aabbccdd",
        created_at=datetime(2026, 6, 2, 1, 2, 9, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        eval_id="20260602T010204Z-feedface",
        failure_categories=("rubric",),
        retry_strategy="Retry after improving rubric evidence.",
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

    assert manifest_path == tmp_path / manifest.name / "capability.yaml"
    assert loaded == manifest
    package_dir = tmp_path / manifest.name
    assert package_dir.joinpath("instructions.md").exists()
    assert package_dir.joinpath("harness.yaml").exists()
    assert package_dir.joinpath("README.md").exists()


def test_list_manifests_reads_capability_registry_entries(tmp_path: Path) -> None:
    manifest = make_manifest()

    manifest_path = write_manifest(manifest, tmp_path)
    listed = list_manifests(tmp_path)

    assert listed == ((manifest_path, manifest),)


def test_load_manifest_rejects_missing_and_corrupt_yaml(tmp_path: Path) -> None:
    with pytest.raises(ManifestNotFoundError):
        load_manifest("missing_capability", tmp_path)

    corrupt_path = tmp_path / "repo_issue" / "capability.yaml"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(ManifestParseError):
        load_manifest("repo_issue", tmp_path)


def test_load_manifest_reads_legacy_manifest_yaml(tmp_path: Path) -> None:
    manifest = make_manifest()
    legacy_path = tmp_path / manifest.name / "manifest.yaml"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        "name: repo_issue\n"
        "version: 0.1.0\n"
        "description: GitHub issue triage capability\n"
        "status: candidate\n"
        "source_evidence_id: 20260602T010203Z-deadbeef\n"
        "normalized_goal: triage repo issue\n"
        "inputs:\n"
        "  - goal\n"
        "workflow:\n"
        "  graph: langgraph\n"
        "  nodes:\n"
        "    - load_evidence\n"
        "harness:\n"
        "  status: pass\n"
        "  checks:\n"
        "    - schema_valid\n"
        "runtime:\n"
        "  name: codex\n"
        "  model: null\n"
        "promotion_criteria:\n"
        "  min_success_runs: 3\n"
        "  max_human_intervention_rate: 0.3\n"
        "  required_harness_pass_rate: 0.9\n",
        encoding="utf-8",
    )

    assert load_manifest(manifest.name, tmp_path).name == manifest.name
    assert list_manifests(tmp_path)[0][0] == legacy_path


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


def test_list_eval_results_reads_eval_registry_entries(tmp_path: Path) -> None:
    result = make_eval_result()

    write_eval_result(result, tmp_path)
    listed = list_eval_results(tmp_path)

    assert listed == (result,)


def test_load_eval_result_reads_eval_by_id(tmp_path: Path) -> None:
    result = make_eval_result()

    write_eval_result(result, tmp_path)
    loaded = load_eval_result(result.id, tmp_path)

    assert loaded == result


def test_write_human_review_persists_json_and_refuses_duplicate(
    tmp_path: Path,
) -> None:
    record = make_human_review_record()

    review_path = write_human_review(record, tmp_path)
    expected_json = record.model_dump_json(indent=2) + "\n"

    assert review_path.read_text(encoding="utf-8") == expected_json
    with pytest.raises(DuplicateWriteError):
        write_human_review(record, tmp_path)


def test_write_learning_export_persists_json_and_refuses_duplicate(
    tmp_path: Path,
) -> None:
    export = make_learning_export()

    learning_path = write_learning_export(export, tmp_path)
    expected_json = export.model_dump_json(indent=2) + "\n"

    assert learning_path.read_text(encoding="utf-8") == expected_json
    with pytest.raises(DuplicateWriteError):
        write_learning_export(export, tmp_path)


def test_write_context_bundle_persists_json_and_refuses_duplicate(
    tmp_path: Path,
) -> None:
    bundle = make_context_bundle()

    context_path = write_context_bundle(bundle, tmp_path)
    expected_json = bundle.model_dump_json(indent=2) + "\n"

    assert context_path.read_text(encoding="utf-8") == expected_json
    with pytest.raises(DuplicateWriteError):
        write_context_bundle(bundle, tmp_path)


def test_write_reflection_report_persists_json_and_refuses_duplicate(
    tmp_path: Path,
) -> None:
    report = make_reflection_report()

    reflection_path = write_reflection_report(report, tmp_path)
    expected_json = report.model_dump_json(indent=2) + "\n"

    assert reflection_path.read_text(encoding="utf-8") == expected_json
    with pytest.raises(DuplicateWriteError):
        write_reflection_report(report, tmp_path)


def test_write_workflow_run_updates_checkpoint_atomically(tmp_path: Path) -> None:
    record = make_workflow_run()

    run_path = write_workflow_run(record, tmp_path)
    updated = record.model_copy(update={"status": "completed", "current_node": None})
    updated_path = write_workflow_run(updated, tmp_path)
    loaded = load_workflow_run(record.id, tmp_path)

    assert run_path == updated_path
    assert loaded.status == "completed"
