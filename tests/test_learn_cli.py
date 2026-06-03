from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    LearningExport,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import (
    load_learning_patch_decision,
    load_manifest,
    write_evidence,
    write_manifest,
)


class LearnOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learning_id: str
    learning_path: str
    capability_name: str


class LearningPatchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    decision_path: str
    capability_name: str
    decision: str
    patch_kind: str
    manifest_path: str | None


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        normalized_goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="0" * 64,
            ),
            CapturedTextFile(
                role="command_output",
                path="output.txt",
                content="Fixed parser branch.",
                size_bytes=20,
                sha256="1" * 64,
            ),
        ),
        errors=("test failed before parser fix",),
        feedback=("prefer smaller diffs",),
        user_interventions=("user added edge case",),
        improvement_notes=("always run parser regression tests",),
        success_or_failure_label="failure",
        harness=HarnessResult(
            status="fail",
            checks=("schema_valid",),
            failures=("regression_missing",),
        ),
    )


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=("parse_goal",)),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def test_learn_exports_evidence_as_learning_assets(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    learning_dir = tmp_path / "learning"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "learn",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--learning-dir",
            str(learning_dir),
        ],
    )

    assert result.exit_code == 0
    output = LearnOutput.model_validate_json(result.stdout)
    export = LearningExport.model_validate_json(
        Path(output.learning_path).read_text(encoding="utf-8"),
    )
    assert output.capability_name == manifest.name
    assert export.prompt_improvement_candidates == (
        "always run parser regression tests",
        "prefer smaller diffs",
    )
    assert export.regression_eval_candidates == (
        "test failed before parser fix",
        "regression_missing",
    )
    assert export.few_shot_examples
    assert export.preference_signals == (
        "prefer smaller diffs",
        "user added edge case",
    )
    assert export.prompt_patches == (
        "Add instruction: always run parser regression tests",
        "Add instruction: prefer smaller diffs",
    )
    assert export.context_patches == (
        "Add context preference: prefer smaller diffs",
        "Add context preference: user added edge case",
    )
    assert export.harness_patches == (
        "Add regression harness: test failed before parser fix",
        "Add regression harness: regression_missing",
    )
    assert export.eval_set_candidates == (
        "goal: triage repo issue\nregression: test failed before parser fix",
        "goal: triage repo issue\nregression: regression_missing",
    )
    assert export.fine_tuning_candidates == export.few_shot_examples
    assert export.fine_tuning_export_format == "jsonl"
    assert export.preference_dataset_candidates == export.preference_signals
    assert export.preference_dataset_schema == (
        "prompt,accepted_output,rejected_output,source_evidence_id"
    )
    assert export.integrity_chain[-1].artifact_type == "learning"


def test_learn_patch_accepts_and_rejects_prompt_patches(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    learning_dir = tmp_path / "learning"
    learning_patch_dir = tmp_path / "learning_patches"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)
    learn_result = CliRunner().invoke(
        app,
        [
            "learn",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--learning-dir",
            str(learning_dir),
        ],
    )
    learning_id = LearnOutput.model_validate_json(learn_result.stdout).learning_id

    accept_result = CliRunner().invoke(
        app,
        [
            "learn-patch",
            manifest.name,
            "--learning-id",
            learning_id,
            "--patch-index",
            "1",
            "--decision",
            "accept",
            "--reviewer",
            "operator",
            "--capabilities-dir",
            str(capabilities_dir),
            "--learning-dir",
            str(learning_dir),
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )

    assert accept_result.exit_code == 0
    accept_output = LearningPatchOutput.model_validate_json(accept_result.stdout)
    updated_manifest = load_manifest(manifest.name, capabilities_dir)
    accepted_decision = load_learning_patch_decision(
        accept_output.decision_id,
        learning_patch_dir,
    )
    assert accept_output.decision == "accepted"
    assert accept_output.patch_kind == "prompt"
    assert updated_manifest.patches.prompt == (
        "Add instruction: always run parser regression tests",
    )
    assert updated_manifest.integrity_chain[-1].artifact_type == "capability"
    assert accepted_decision.integrity_chain[-1].artifact_type == (
        "learning_patch_decision"
    )

    reject_result = CliRunner().invoke(
        app,
        [
            "learn-patch",
            manifest.name,
            "--learning-id",
            learning_id,
            "--patch-index",
            "2",
            "--decision",
            "reject",
            "--note",
            "too broad",
            "--capabilities-dir",
            str(capabilities_dir),
            "--learning-dir",
            str(learning_dir),
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )

    assert reject_result.exit_code == 0
    reject_output = LearningPatchOutput.model_validate_json(reject_result.stdout)
    rejected_decision = load_learning_patch_decision(
        reject_output.decision_id,
        learning_patch_dir,
    )
    assert reject_output.decision == "rejected"
    assert reject_output.patch_kind == "prompt"
    assert reject_output.manifest_path is None
    assert rejected_decision.notes == ("too broad",)
    assert load_manifest(manifest.name, capabilities_dir).patches.prompt == (
        "Add instruction: always run parser regression tests",
    )


def test_learn_patch_accepts_context_and_harness_patches(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    learning_dir = tmp_path / "learning"
    learning_patch_dir = tmp_path / "learning_patches"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)
    learn_result = CliRunner().invoke(
        app,
        [
            "learn",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--learning-dir",
            str(learning_dir),
        ],
    )
    learning_id = LearnOutput.model_validate_json(learn_result.stdout).learning_id

    context_result = CliRunner().invoke(
        app,
        [
            "learn-patch",
            manifest.name,
            "--learning-id",
            learning_id,
            "--patch-index",
            "1",
            "--patch-kind",
            "context",
            "--decision",
            "accept",
            "--capabilities-dir",
            str(capabilities_dir),
            "--learning-dir",
            str(learning_dir),
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )
    harness_result = CliRunner().invoke(
        app,
        [
            "learn-patch",
            manifest.name,
            "--learning-id",
            learning_id,
            "--patch-index",
            "1",
            "--patch-kind",
            "harness",
            "--decision",
            "accept",
            "--capabilities-dir",
            str(capabilities_dir),
            "--learning-dir",
            str(learning_dir),
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )

    assert context_result.exit_code == 0
    assert harness_result.exit_code == 0
    context_output = LearningPatchOutput.model_validate_json(context_result.stdout)
    harness_output = LearningPatchOutput.model_validate_json(harness_result.stdout)
    updated_manifest = load_manifest(manifest.name, capabilities_dir)
    context_decision = load_learning_patch_decision(
        context_output.decision_id,
        learning_patch_dir,
    )
    harness_decision = load_learning_patch_decision(
        harness_output.decision_id,
        learning_patch_dir,
    )
    assert context_output.patch_kind == "context"
    assert harness_output.patch_kind == "harness"
    assert updated_manifest.patches.context == (
        "Add context preference: prefer smaller diffs",
    )
    assert updated_manifest.patches.harness == (
        "Add regression harness: test failed before parser fix",
    )
    assert context_decision.patch_kind == "context"
    assert harness_decision.patch_kind == "harness"
