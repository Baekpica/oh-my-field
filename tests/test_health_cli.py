from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_manifest


class HealthOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str | None = None
    count: int
    entries: list[dict[str, object]]


class HardenOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    recommended_actions: tuple[str, ...]


class CardOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    card_path: str
    written: bool
    content: str


def test_health_reports_next_action(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "health",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
        ],
    )

    assert result.exit_code == 0
    output = HealthOutput.model_validate_json(result.stdout)
    entry = output.entries[0]
    assert output.capability_name == "repo_issue_triage"
    assert entry["export_status"] == "not_exported"
    assert entry["import_status"] == "not_imported"
    assert entry["validation_status"] == "not_run"
    assert entry["next_action"] == "run `omf verify capability repo_issue_triage`"


def test_harden_recommends_eval_export_and_learning_review(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "harden",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
        ],
    )

    assert result.exit_code == 0
    output = HardenOutput.model_validate_json(result.stdout)
    eval_action = (
        "run `omf eval repo_issue_triage --eval-set repo_issue_triage_regression`"
    )
    assert eval_action in output.recommended_actions
    assert "export to Codex, Claude Code, Hermes, or generic target" in (
        output.recommended_actions
    )
    assert "review learning patch candidates after `omf learn`" in (
        output.recommended_actions
    )


def test_card_reads_and_rewrites_capability_card(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    read_result = CliRunner().invoke(
        app,
        [
            "card",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )
    write_result = CliRunner().invoke(
        app,
        [
            "card",
            "repo_issue_triage",
            "--write",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert read_result.exit_code == 0
    assert write_result.exit_code == 0
    read_output = CardOutput.model_validate_json(read_result.stdout)
    write_output = CardOutput.model_validate_json(write_result.stdout)
    assert "## What It Does" in read_output.content
    assert not read_output.written
    assert write_output.written
    assert Path(write_output.card_path).exists()


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=("import_evidence",)),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5", tools=("shell",)),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )
