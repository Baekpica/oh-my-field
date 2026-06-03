from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    ContextPolicy,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowControl,
    WorkflowManifest,
)
from oh_my_field.storage import load_manifest, write_manifest


class CapabilityExportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    export_path: str
    portability_path: str
    runtime_export_path: str
    target_runtime: str
    target_model: str | None


class CapabilityImportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    imported_package_path: str
    validation_report_path: str
    status: str
    tool_compatibility: str
    portability_score: float
    eval_id: str | None
    eval_path: str | None
    failure_evidence_id: str | None
    failure_evidence_path: str | None


def test_capability_export_writes_portability_bundle(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    export_dir = tmp_path / "exports" / "repo_issue_triage-hermes"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--source-project",
            "source-repo",
            "--target-project",
            "target-repo",
            "--source-context-tokens",
            "64000",
            "--target-context-tokens",
            "16000",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityExportOutput.model_validate_json(result.stdout)
    portability = yaml.safe_load(
        Path(output.portability_path).read_text(encoding="utf-8"),
    )
    assert output.capability_name == "repo_issue_triage"
    assert output.target_runtime == "hermes"
    assert output.target_model == "qwen3.6-27b"
    assert Path(output.export_path) == export_dir
    assert export_dir.joinpath("capability.yaml").exists()
    assert export_dir.joinpath("instructions", "base.md").exists()
    assert export_dir.joinpath("instructions", "compact.md").exists()
    assert export_dir.joinpath(
        "instructions",
        "model_notes.qwen3.6-27b.md",
    ).exists()
    assert export_dir.joinpath("context", "context.policy.yaml").exists()
    assert export_dir.joinpath("context", "context.pack.md").exists()
    assert export_dir.joinpath("harness", "harness.yaml").exists()
    assert export_dir.joinpath("provenance", "source_runtime.yaml").exists()
    assert export_dir.joinpath("runtime", "hermes").exists()
    assert portability["source"]["runtime"] == "codex"
    assert portability["source"]["model"] == "gpt-5.5"
    assert portability["source"]["project"] == "source-repo"
    assert portability["target"]["runtime"] == "hermes"
    assert portability["target"]["model"] == "qwen3.6-27b"
    assert portability["target"]["project"] == "target-repo"
    assert portability["compatibility"]["compression_required"]
    assert portability["compatibility"]["context_budget"]["source_tokens"] == 64000
    assert portability["compatibility"]["context_budget"]["target_tokens"] == 16000
    assert "cross_runtime" in portability["adaptation"]["transfer_type"]
    assert "project_transfer" in portability["adaptation"]["transfer_type"]


def test_capability_import_writes_validation_report(tmp_path: Path) -> None:
    source_capabilities_dir = tmp_path / "source-capabilities"
    export_dir = tmp_path / "exports" / "repo_issue_triage-generic"
    target_capabilities_dir = tmp_path / "target-capabilities"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_capabilities_dir)
    export_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "generic",
            "--target-model",
            "small-local",
            "--target-project",
            "target-repo",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_capabilities_dir),
        ],
    )
    assert export_result.exit_code == 0

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "generic",
            "--model",
            "small-local",
            "--project",
            "target-repo",
            "--available-tool",
            "file_system",
            "--validate",
            "--capabilities-dir",
            str(target_capabilities_dir),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    report = yaml.safe_load(
        Path(output.validation_report_path).read_text(encoding="utf-8"),
    )
    imported = load_manifest("repo_issue_triage", target_capabilities_dir)
    assert output.status == "needs_adaptation"
    assert output.tool_compatibility == "partial"
    assert output.portability_score == 0.45
    assert output.eval_id is not None
    assert output.eval_path is not None
    assert output.failure_evidence_id is not None
    assert output.failure_evidence_path is not None
    assert imported.name == "repo_issue_triage"
    assert Path(output.imported_package_path).joinpath("capability.yaml").exists()
    assert Path(output.eval_path).exists()
    assert Path(output.failure_evidence_path).exists()
    assert report["target"]["runtime"] == "generic"
    assert report["target"]["model"] == "small-local"
    assert report["context_remap_required"]
    assert report["unavailable_tools"] == ["shell"]
    assert report["portability_score"] == 0.45
    assert report["model_delta"]["model_changed"]
    assert report["eval_id"] == output.eval_id
    assert report["failure_evidence_id"] == output.failure_evidence_id


@pytest.mark.parametrize(
    ("target", "expected_files"),
    [
        (
            "codex",
            (
                "AGENTS.md",
                "capability.md",
                "context.policy.md",
                "harness.md",
            ),
        ),
        (
            "claude_code",
            (
                "CLAUDE.md",
                "capability.md",
                "examples.md",
                "checks.md",
            ),
        ),
        (
            "hermes",
            (
                "SOUL.md",
                "skills/repo_issue_triage.md",
                "profile.patch.yaml",
                "harness.md",
            ),
        ),
        (
            "generic",
            (
                "skill.md",
                "context.policy.yaml",
                "harness.yaml",
                "eval_set.yaml",
            ),
        ),
    ],
)
def test_capability_export_writes_runtime_specific_skill_assets(
    tmp_path: Path,
    target: str,
    expected_files: tuple[str, ...],
) -> None:
    capabilities_dir = tmp_path / f"{target}-capabilities"
    export_dir = tmp_path / "exports" / target
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            target,
            "--target-model",
            "target-model",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    runtime_dir = export_dir / "runtime" / target
    for expected_file in expected_files:
        assert runtime_dir.joinpath(expected_file).exists()


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        source_evidence_ids=("20260602T010203Z-deadbeef",),
        normalized_goal="triage repo issue",
        inputs=("goal",),
        context=ContextPolicy(
            required=("AGENTS.md",),
            forbidden=(".env", "secrets/"),
        ),
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("import_evidence", "run_verification"),
        ),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid",),
            required_checks=("schema_valid",),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5", tools=("shell",)),
        workflow_control=WorkflowControl(allowed_tools=("shell",)),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )
