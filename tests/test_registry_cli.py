from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    EvalCheck,
    EvalResult,
    HarnessResult,
    PromotionCriteria,
    PromotionMetrics,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_eval_result, write_manifest


class RegistryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str | None = None
    count: int
    registry: dict[str, object]


def test_registry_lists_capabilities_with_eval_results(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    eval_dir = tmp_path / "evals"
    manifest = make_manifest()
    eval_result = make_eval_result()
    write_manifest(manifest, capabilities_dir)
    write_eval_result(eval_result, eval_dir)

    result = CliRunner().invoke(
        app,
        [
            "registry",
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(eval_dir),
        ],
    )

    assert result.exit_code == 0
    output = RegistryOutput.model_validate_json(result.stdout)
    entries = output.registry["entries"]
    assert output.count == 1
    assert isinstance(entries, list)
    assert entries[0]["name"] == "repo_issue_triage"
    assert entries[0]["evaluation_results"] == [eval_result.id]
    assert "runtime:codex" in entries[0]["runtime_compatibility"]
    assert entries[0]["eval_count"] == 1
    assert entries[0]["latest_eval_status"] == "pass"
    assert entries[0]["pass_rate"] == 1.0
    assert entries[0]["source_evidence_count"] == 1
    assert entries[0]["runtime_profiles"] == ["codex:gpt-5.5"]
    assert entries[0]["promotion_success_runs"] == 3
    assert entries[0]["promotion_harness_pass_rate"] == 1.0
    assert entries[0]["promotion_eval_pass_rate"] == 1.0
    assert entries[0]["promotion_criteria_met"]
    assert entries[0]["integrity_status"] == "fail"
    assert entries[0]["next_action"] == "run `omf verify capability repo_issue_triage`"


def test_registry_filters_to_single_capability(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    manifest = make_manifest()
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "registry",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
        ],
    )

    assert result.exit_code == 0
    output = RegistryOutput.model_validate_json(result.stdout)
    assert output.capability_name == manifest.name
    assert output.count == 1


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        owner="platform",
        dependencies=("pytest",),
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
        promotion_metrics=PromotionMetrics(
            evidence_count=3,
            successful_evidence_count=3,
            failed_evidence_count=0,
            harness_pass_rate=1.0,
            human_intervention_rate=0.0,
            retry_rate=0.0,
            eval_count=1,
            eval_pass_rate=1.0,
            runtime_profiles=("runtime:codex",),
            criteria_met=True,
        ),
    )


def make_eval_result() -> EvalResult:
    return EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        status="pass",
        checks=(EvalCheck(name="schema_valid", status="pass", message="ok"),),
    )
