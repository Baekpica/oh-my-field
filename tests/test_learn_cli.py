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
from oh_my_field.storage import write_evidence, write_manifest


class LearnOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learning_id: str
    learning_path: str
    capability_name: str


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
    assert export.eval_set_candidates == (
        "goal: triage repo issue\nregression: test failed before parser fix",
        "goal: triage repo issue\nregression: regression_missing",
    )
    assert export.fine_tuning_candidates == export.few_shot_examples
    assert export.preference_dataset_candidates == export.preference_signals
