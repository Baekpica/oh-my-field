from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    EvalCheck,
    EvalChecklistItem,
    EvalResult,
    EvalRubricScore,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    ReflectionReport,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_eval_result, write_evidence, write_manifest


class ReflectOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reflection_id: str
    reflection_path: str
    capability_name: str
    eval_id: str | None = None


def test_reflect_creates_failure_analysis_from_eval_result(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    eval_dir = tmp_path / "evals"
    reflection_dir = tmp_path / "reflections"
    evidence = make_evidence_record()
    manifest = make_manifest()
    eval_result = make_eval_result()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)
    write_eval_result(eval_result, eval_dir)

    result = CliRunner().invoke(
        app,
        [
            "reflect",
            manifest.name,
            "--eval-id",
            eval_result.id,
            "--note",
            "operator saw repeated issue",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--eval-dir",
            str(eval_dir),
            "--reflection-dir",
            str(reflection_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReflectOutput.model_validate_json(result.stdout)
    report = ReflectionReport.model_validate_json(
        Path(output.reflection_path).read_text(encoding="utf-8"),
    )
    assert output.eval_id == eval_result.id
    assert report.failure_categories == (
        "eval_harness",
        "checklist",
        "rubric",
    )
    assert report.prompt_patches == (
        "Add checklist requirement: approval attached",
        "Improve rubric dimension clarity to at least 3",
    )
    assert report.notes == ("operator saw repeated issue",)


def test_reflect_without_eval_uses_source_evidence_only(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    reflection_dir = tmp_path / "reflections"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "reflect",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--reflection-dir",
            str(reflection_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReflectOutput.model_validate_json(result.stdout)
    report = ReflectionReport.model_validate_json(
        Path(output.reflection_path).read_text(encoding="utf-8"),
    )
    assert report.eval_id is None
    assert report.failure_categories == ()
    assert report.retry_strategy.startswith("No retry needed")


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
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


def make_eval_result() -> EvalResult:
    return EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        status="fail",
        checks=(EvalCheck(name="approval", status="fail", message="missing"),),
        failures=("missing approval",),
        checklist_items=(
            EvalChecklistItem(
                name="approval attached",
                status="fail",
                message="checklist item failed: approval attached",
            ),
        ),
        rubric_scores=(
            EvalRubricScore(
                name="clarity",
                score=2,
                max_score=5,
                pass_threshold=3,
                status="fail",
                message="needs clearer evidence",
            ),
        ),
    )
