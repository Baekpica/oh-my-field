from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    ArtifactContract,
    CapturedTextFile,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    RecordQuality,
    RuntimeInfo,
    TaskContract,
    ValidationCheckResult,
)
from oh_my_field.storage import load_manifest, write_eval_result, write_evidence


class PromoteOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    manifest_path: str
    package_path: str
    capability_path: str
    instructions_path: str
    harness_path: str
    card_path: str
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
        final_artifacts=("output/report.json",),
        harness=HarnessResult(
            status="pass",
            checks=("files_readable", "schema_valid"),
            failures=(),
        ),
        validation_results=(
            ValidationCheckResult(
                name="artifact_exists:output/report.json",
                status="pass",
                message="artifact exists",
                artifact_path="output/report.json",
            ),
        ),
        artifact_contracts=(
            ArtifactContract(
                name="output_report_json",
                artifact_path="output/report.json",
                artifact_kind="json",
                validation_checks=("artifact_exists:output/report.json",),
            ),
        ),
        task_contract=TaskContract(
            goal="triage repo issue",
            required_inputs=("prompt.md",),
            expected_artifacts=("output/report.json",),
            validation_checks=("artifact_exists:output/report.json",),
        ),
        record_quality=RecordQuality(score=1.0, strict_ready=True),
        task_outcome="success",
        success_or_failure_label="success",
    )


def make_evidence_record_with_id(evidence_id: str) -> EvidenceRecord:
    return make_evidence_record().model_copy(update={"id": evidence_id})


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
    package_path = capabilities_dir / "repo_issue_triage"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert output.capability_name == "repo_issue_triage"
    assert output.status == "candidate"
    _assert_package_output(output, package_path)
    assert "schema_version: omf.capability.v0.1" in manifest_text
    assert "name: repo_issue_triage" in manifest_text
    assert f"source_evidence_id: {evidence.id}" in manifest_text
    assert f"- {evidence.id}" in manifest_text
    manifest = load_manifest("repo_issue_triage", capabilities_dir)
    assert manifest.source_evidence_ids == (evidence.id,)
    assert manifest.promotion_metrics is not None
    assert manifest.promotion_metrics.evidence_count == 1
    assert manifest.promotion_metrics.harness_pass_rate == 1.0
    assert manifest.promotion_metrics.eval_gate_met
    assert manifest.field is not None
    assert manifest.field.name == "local"
    assert manifest.field.policies.forbidden_context == (
        ".env",
        "secrets/",
        "production-kubeconfig",
    )
    assert manifest.context.sources[0].type == "evidence"
    assert manifest.integrity_chain[-2].artifact_type == "evidence"
    assert manifest.integrity_chain[-1].artifact_type == "capability"
    assert manifest.integrity_chain[-1].previous_sha256 == (
        manifest.integrity_chain[-2].sha256
    )
    assert manifest.workflow.nodes == (
        "import_evidence",
        "pack_context",
        "run_verification",
        "record_review",
        "export_runtime_assets",
        "apply_learning_patch",
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
        "privilege_escalation",
    )
    assert manifest.workflow_control.safe_execution_mode
    assert manifest.workflow_control.network_policy == "disabled"
    assert manifest.workflow_control.require_approval_before_destructive_action
    assert "approval_required_actions:" in manifest_text
    assert "safe_execution_mode: true" in manifest_text
    assert "network_policy: disabled" in manifest_text


def _assert_package_output(output: PromoteOutput, package_path: Path) -> None:
    assert Path(output.manifest_path) == package_path / "capability.yaml"
    assert Path(output.package_path) == package_path
    assert Path(output.capability_path) == package_path / "capability.yaml"
    assert Path(output.instructions_path) == package_path / "instructions.md"
    assert Path(output.harness_path) == package_path / "harness.yaml"
    assert Path(output.card_path) == package_path / "README.md"
    assert (package_path / "instructions.md").exists()
    assert (package_path / "harness.yaml").exists()
    assert (package_path / "README.md").exists()
    assert (package_path / "contracts" / "task_contract.yaml").exists()
    assert (package_path / "contracts" / "artifacts.yaml").exists()
    assert (package_path / "contracts" / "validation.md").exists()
    assert (package_path / "contracts" / "replay_plan.yaml").exists()
    assert (package_path / "validators" / "validate_contract.py").exists()
    card_text = (package_path / "README.md").read_text(encoding="utf-8")
    instructions_text = (package_path / "instructions.md").read_text(
        encoding="utf-8",
    )
    assert "## Package Contents" in card_text
    assert "runtime-neutral agent instruction surface" in card_text
    assert "Treat the package as the source of truth" in instructions_text


def test_promote_rejects_weak_evidence_by_default(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record().model_copy(
        update={
            "artifact_contracts": (),
            "task_contract": None,
            "record_quality": None,
            "validation_results": (),
        },
    )
    write_evidence(evidence, evidence_dir)

    result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "weak_repo_issue_triage",
            "--description",
            "Weak evidence should not promote under strict gate",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code != 0
    assert "strict quality gate" in result.stderr
    assert "--no-strict" in result.stderr


def test_promote_allows_weak_evidence_with_no_strict(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record().model_copy(
        update={
            "artifact_contracts": (),
            "task_contract": None,
            "record_quality": None,
            "validation_results": (),
        },
    )
    write_evidence(evidence, evidence_dir)

    result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "weak_repo_issue_triage",
            "--description",
            "Weak evidence with explicit relaxed gate",
            "--no-strict",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = PromoteOutput.model_validate_json(result.stdout)
    assert output.capability_name == "weak_repo_issue_triage"


def test_promote_creates_manifest_from_evidence_set(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence_ids = (
        "20260602T010203Z-deadbeef",
        "20260602T010204Z-feedface",
        "20260602T010205Z-cafebabe",
    )
    for evidence_id in evidence_ids:
        write_evidence(make_evidence_record_with_id(evidence_id), evidence_dir)
    evidence_set_path = tmp_path / "evidence-set.yaml"
    evidence_set_path.write_text(
        "evidence_ids:\n"
        + "".join(f"  - {evidence_id}\n" for evidence_id in evidence_ids),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "promote",
            "--from-evidence-set",
            str(evidence_set_path),
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
    manifest = load_manifest(output.capability_name, capabilities_dir)
    assert manifest.status == "validated"
    assert manifest.source_evidence_ids == evidence_ids
    assert manifest.promotion_metrics is not None
    assert manifest.promotion_metrics.criteria_met
    assert manifest.promotion_metrics.successful_evidence_count == 3
    assert len(manifest.integrity_chain) == 4


def test_promote_does_not_count_unknown_harness_pass_as_success(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record().model_copy(
        update={
            "task_outcome": "unknown",
            "success_or_failure_label": "unknown",
        },
    )
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
    manifest = load_manifest(output.capability_name, capabilities_dir)
    assert manifest.promotion_metrics is not None
    assert manifest.promotion_metrics.harness_pass_rate == 1.0
    assert manifest.promotion_metrics.successful_evidence_count == 0


def test_promote_uses_eval_results_for_stable_status(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    eval_dir = tmp_path / "evals"
    capabilities_dir = tmp_path / "capabilities"
    evidence_ids = (
        "20260602T010203Z-deadbeef",
        "20260602T010204Z-feedface",
        "20260602T010205Z-cafebabe",
    )
    for evidence_id in evidence_ids:
        write_evidence(make_evidence_record_with_id(evidence_id), evidence_dir)
    write_eval_result(
        EvalResult(
            id="20260602T010206Z-f00dbabe",
            created_at=datetime(2026, 6, 2, 1, 2, 6, tzinfo=UTC),
            capability_name="repo_issue_triage",
            source_evidence_id=evidence_ids[0],
            runtime_profile="codex",
            status="pass",
            checks=(EvalCheck(name="schema_valid", status="pass", message="ok"),),
        ),
        eval_dir,
    )
    evidence_set_path = tmp_path / "evidence-set.yaml"
    evidence_set_path.write_text(
        "".join(f"- {evidence_id}\n" for evidence_id in evidence_ids),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "promote",
            "--from-evidence-set",
            str(evidence_set_path),
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--eval-dir",
            str(eval_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = PromoteOutput.model_validate_json(result.stdout)
    manifest = load_manifest(output.capability_name, capabilities_dir)
    assert manifest.status == "stable"
    assert manifest.promotion_metrics is not None
    assert manifest.promotion_metrics.eval_count == 1
    assert manifest.promotion_metrics.eval_pass_rate == 1.0


def test_promote_refuses_duplicate_capability_name(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    write_evidence(evidence, evidence_dir)
    capability_path = capabilities_dir / "repo_issue_triage" / "capability.yaml"
    capability_path.parent.mkdir(parents=True)
    capability_path.write_text("name: repo_issue_triage\n", encoding="utf-8")

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
