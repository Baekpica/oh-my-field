import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    HarnessResult,
    LearningPatchDecision,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_learning_patch_decision, write_manifest


def test_explain_learning_patch_reports_evidence_and_status(tmp_path: Path) -> None:
    learning_patch_dir = tmp_path / "learning_patches"
    decision = make_learning_patch()
    write_learning_patch_decision(decision, learning_patch_dir)

    result = CliRunner().invoke(
        app,
        [
            "explain",
            "learning-patch",
            decision.id,
            "--learning-patch-dir",
            str(learning_patch_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["subject"] == "Always run pytest."
    assert output["current_status"] == "accepted"
    assert output["evidence"] == ["20260602T010204Z-feedface"]
    assert output["payload"]["patch_kind"] == "harness"


def test_explain_harness_reports_check_origin(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "explain",
            "harness",
            "repo_issue",
            "--check",
            "pytest",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["subject"] == "pytest"
    assert output["current_status"] == "pass"
    assert output["payload"]["check_present"]
    assert output["payload"]["required"]
    assert "harness_patch:Always run pytest." in output["introduced_by"]


def test_why_alias_explains_capability_rule(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "why",
            "capability",
            "repo_issue",
            "--rule",
            "pytest",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["target_type"] == "capability"
    assert output["subject"] == "pytest"
    assert output["current_status"] == "candidate"
    assert output["payload"]["matches"]["harness_checks"] == ["pytest"]


def make_manifest() -> CapabilityManifest:
    manifest = CapabilityManifest(
        name="repo_issue",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=("load_evidence",)),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid", "pytest"),
            required_checks=("schema_valid", "pytest"),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )
    patches = manifest.patches.model_copy(update={"harness": ("Always run pytest.",)})
    return manifest.model_copy(update={"patches": patches})


def make_learning_patch() -> LearningPatchDecision:
    return LearningPatchDecision(
        id="20260602T010205Z-cafebabe",
        created_at=datetime(2026, 6, 2, 1, 2, 5, tzinfo=UTC),
        capability_name="repo_issue",
        learning_id="20260602T010204Z-feedface",
        patch_kind="harness",
        patch="Always run pytest.",
        decision="accepted",
    )


def _json(text: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(text))
