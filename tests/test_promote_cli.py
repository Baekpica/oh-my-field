from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
)
from oh_my_field.storage import load_manifest, write_evidence


class PromoteOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    manifest_path: str
    status: str


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
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
        ),
        feedback=("looks reusable",),
        harness=HarnessResult(
            status="pass",
            checks=("files_readable", "schema_valid"),
            failures=(),
        ),
    )


def test_promote_creates_capability_manifest_from_evidence(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    write_evidence(evidence, evidence_dir)

    result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = PromoteOutput.model_validate_json(result.stdout)
    manifest_path = Path(output.manifest_path)
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert output.capability_name == "repo_issue_triage"
    assert output.status == "candidate"
    assert manifest_path == capabilities_dir / "repo_issue_triage" / "manifest.yaml"
    assert "name: repo_issue_triage" in manifest_text
    assert f"source_evidence_id: {evidence.id}" in manifest_text
    manifest = load_manifest("repo_issue_triage", capabilities_dir)
    assert manifest.workflow.nodes == (
        "parse_goal",
        "collect_context",
        "plan_execution",
        "execute_tools",
        "run_harness",
        "collect_evidence",
        "human_review",
        "package_learning",
    )
    assert manifest.harness.human_review_required
    assert manifest.evidence.store
    assert manifest.workflow_control.approval_required_actions == (
        "write",
        "destructive",
        "external_call",
        "credential_access",
        "production_write",
        "paid_operation",
    )
    assert manifest.workflow_control.safe_execution_mode
    assert manifest.workflow_control.network_policy == "disabled"
    assert manifest.workflow_control.require_approval_before_destructive_action
    assert "approval_required_actions:" in manifest_text
    assert "safe_execution_mode: true" in manifest_text
    assert "network_policy: disabled" in manifest_text


def test_promote_refuses_duplicate_capability_name(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    write_evidence(evidence, evidence_dir)
    manifest_path = capabilities_dir / "repo_issue_triage" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("name: repo_issue_triage\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code != 0
    assert "refusing to overwrite existing file" in result.stderr


def test_promote_fails_for_missing_evidence_id(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "promote",
            "20260602T010203Z-deadbeef",
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
        ],
    )

    assert result.exit_code != 0
    assert "not found" in result.stderr
