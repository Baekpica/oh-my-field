from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    LearningPatchDecision,
    PatchDecisionStatus,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import (
    write_evidence,
    write_learning_patch_decision,
    write_manifest,
)


def test_diff_evidence_outputs_unified_diff(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    left = make_evidence("20260602T010203Z-deadbeef", "triage repo issue")
    right = make_evidence("20260602T010204Z-feedface", "fix repo issue")
    write_evidence(left, evidence_dir)
    write_evidence(right, evidence_dir)

    result = CliRunner().invoke(
        app,
        [
            "diff",
            "evidence",
            left.id,
            right.id,
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    assert "--- evidence/20260602T010203Z-deadbeef.json" in result.stdout
    assert "+++ evidence/20260602T010204Z-feedface.json" in result.stdout
    assert '-  "goal": "triage repo issue",' in result.stdout
    assert '+  "goal": "fix repo issue",' in result.stdout


def test_diff_capability_outputs_manifest_diff(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest("repo_issue", "Issue triage"), capabilities_dir)
    write_manifest(make_manifest("repo_issue_v2", "Issue triage v2"), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "diff",
            "capability",
            "repo_issue",
            "repo_issue_v2",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    assert "--- " in result.stdout
    assert "capability.yaml" in result.stdout
    assert "-description: Issue triage" in result.stdout
    assert "+description: Issue triage v2" in result.stdout


def test_diff_harness_compares_same_capability_across_dirs(tmp_path: Path) -> None:
    left_dir = tmp_path / "left"
    right_dir = tmp_path / "right"
    write_manifest(
        make_manifest("repo_issue", "Issue triage", checks=("schema_valid",)),
        left_dir,
    )
    write_manifest(
        make_manifest(
            "repo_issue",
            "Issue triage",
            checks=("schema_valid", "pytest"),
        ),
        right_dir,
    )

    result = CliRunner().invoke(
        app,
        [
            "diff",
            "harness",
            "repo_issue",
            "--from-capabilities-dir",
            str(left_dir),
            "--to-capabilities-dir",
            str(right_dir),
        ],
    )

    assert result.exit_code == 0
    assert "harness.yaml" in result.stdout
    assert "+- pytest" in result.stdout


def test_diff_learning_patch_outputs_decision_diff(tmp_path: Path) -> None:
    learning_patch_dir = tmp_path / "learning_patches"
    left = make_learning_patch("20260602T010205Z-cafebabe", "accepted")
    right = make_learning_patch("20260602T010206Z-baddcafe", "rejected")
    write_learning_patch_decision(left, learning_patch_dir)
    write_learning_patch_decision(right, learning_patch_dir)

    result = CliRunner().invoke(
        app,
        [
            "diff",
            "learning-patch",
            left.id,
            right.id,
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )

    assert result.exit_code == 0
    assert '-  "decision": "accepted",' in result.stdout
    assert '+  "decision": "rejected",' in result.stdout


def make_evidence(evidence_id: str, goal: str) -> EvidenceRecord:
    return EvidenceRecord(
        id=evidence_id,
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal=goal,
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content=goal,
                size_bytes=len(goal),
                sha256="0" * 64,
            ),
        ),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
    )


def make_manifest(
    name: str,
    description: str,
    *,
    checks: tuple[str, ...] = ("schema_valid",),
) -> CapabilityManifest:
    return CapabilityManifest(
        name=name,
        version="0.1.0",
        description=description,
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=("load_evidence",)),
        harness=HarnessResult(status="pass", checks=checks, required_checks=checks),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def make_learning_patch(
    decision_id: str,
    decision: PatchDecisionStatus,
) -> LearningPatchDecision:
    return LearningPatchDecision(
        id=decision_id,
        created_at=datetime(2026, 6, 2, 1, 2, 5, tzinfo=UTC),
        capability_name="repo_issue",
        learning_id="20260602T010204Z-feedface",
        patch="Prefer focused issue summaries.",
        decision=decision,
    )
