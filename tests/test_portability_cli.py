import hashlib
import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.integrity import append_integrity_link
from oh_my_field.mcp.tools import dispatch_tool, mcp_tool_definitions
from oh_my_field.models import (
    ArtifactContract,
    CapabilityManifest,
    CapturedTextFile,
    ContextPolicy,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    PromotionMetrics,
    RecordQuality,
    RuntimeInfo,
    TaskContract,
    WorkflowControl,
    WorkflowManifest,
)
from oh_my_field.storage import load_manifest, write_evidence, write_manifest


class CapabilityExportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    export_path: str
    package_path: str
    unpacked_path: str | None
    portability_path: str
    runtime_export_path: str
    target_runtime: str
    target_model: str | None
    bundle_format: str
    evidence_mode: str
    evidence_proof_count: int
    next_action: str


class CapabilityImportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    package_path: str
    unpacked_path: str | None
    imported_package_path: str
    validation_report_path: str
    overlay_path: str
    status: str
    tool_compatibility: str
    portability_readiness_score: float
    eval_id: str | None
    eval_path: str | None
    failure_evidence_id: str | None
    failure_evidence_path: str | None
    next_commands: list[str]


class CapabilityValidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    package_path: str | None
    unpacked_path: str | None
    imported_package_path: str
    overlay_path: str
    validation_report_path: str
    status: str
    tool_compatibility: str
    portability_readiness_score: float
    eval_id: str | None
    eval_path: str | None
    failure_evidence_id: str | None
    failure_evidence_path: str | None
    target_run_executed: bool
    target_run_exit_code: int | None
    manual_run_required: bool
    manual_run_reason: str | None
    next_commands: list[str]


class HardenOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    recommended_actions: list[str]


class CapabilityRemapOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    remap_path: str
    binding_count: int
    unresolved: list[str]
    complete: bool
    next_action: str


class CapabilityAdaptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    overlay_path: str
    instruction_variant: str
    context_variant: str
    required_human_review: bool
    next_action: str


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
    assert export_dir.joinpath("contracts", "task_contract.yaml").exists()
    assert export_dir.joinpath("contracts", "artifacts.yaml").exists()
    assert export_dir.joinpath("contracts", "validation.md").exists()
    assert export_dir.joinpath("contracts", "replay_plan.yaml").exists()
    assert export_dir.joinpath("validators", "validate_contract.py").exists()
    assert export_dir.joinpath("provenance", "source_runtime.yaml").exists()
    assert export_dir.joinpath("runtime", "hermes").exists()
    assert portability["schema_version"] == "omf.portability.v0.1"
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


def test_capability_import_writes_validation_report(  # noqa: PLR0915
    tmp_path: Path,
) -> None:
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
    assert output.portability_readiness_score == 0.65
    assert output.eval_id is not None
    assert output.eval_path is not None
    assert output.failure_evidence_id is not None
    assert output.failure_evidence_path is not None
    assert imported.name == "repo_issue_triage"
    assert Path(output.imported_package_path).joinpath("capability.yaml").exists()
    assert Path(output.eval_path).exists()
    assert Path(output.failure_evidence_path).exists()
    assert report["schema_version"] == "omf.target_validation.v0.2"
    assert report["target"]["runtime"] == "generic"
    assert report["target"]["model"] == "small-local"
    assert report["context_remap_required"]
    assert report["unavailable_tools"] == ["shell"]
    assert report["readiness"]["score"] == 0.65
    assert report["readiness"]["required_pass_rate"] == 0.8
    factor_names = {factor["name"] for factor in report["readiness"]["factors"]}
    assert factor_names == {
        "cross_runtime",
        "model_downgrade",
        "project_transfer",
    }
    assert report["portability_risk"]["score"] == 0.65
    assert report["portability_risk"]["level"] == "medium"
    assert report["portability_risk"]["advisory_only"] is True
    blocker_names = {blocker["name"] for blocker in report["hard_blockers"]}
    assert blocker_names == {"unavailable_tool:shell", "unresolved_context_remap"}
    warning_names = {warning["name"] for warning in report["warnings"]}
    assert warning_names == factor_names
    assert report["model_delta"]["model_changed"]
    assert report["eval_id"] == output.eval_id
    assert report["failure_evidence_id"] == output.failure_evidence_id
    overlay = yaml.safe_load(Path(output.overlay_path).read_text(encoding="utf-8"))
    target_dir = Path(output.overlay_path).parent
    assert overlay["schema_version"] == "omf.target_overlay.v0.2"
    assert overlay["target"]["runtime"] == "generic"
    assert overlay["target"]["model"] == "small-local"
    assert overlay["status"] == "needs_adaptation"
    assert {blocker["name"] for blocker in overlay["hard_blockers"]} == {
        "unavailable_tool:shell",
        "unresolved_context_remap",
    }
    assert overlay["portability_risk"]["score"] == 0.65
    assert overlay["overrides"]["instruction_variant"] == "compact"
    assert overlay["overrides"]["context_variant"] == "full"
    assert overlay["eval_id"] == output.eval_id
    assert overlay["failure_evidence_id"] == output.failure_evidence_id
    assert target_dir.joinpath("README.md").exists()
    assert target_dir.joinpath("instructions.md").exists()
    assert target_dir.joinpath("context.pack.md").exists()
    assert "omf card repo_issue_triage" in output.next_commands


def test_capability_archive_export_import_and_verify_package(tmp_path: Path) -> None:
    source_capabilities_dir = tmp_path / "source-capabilities"
    export_out = tmp_path / "exports" / "repo_issue_triage-hermes"
    target_capabilities_dir = tmp_path / "target-capabilities"
    write_manifest(make_manifest(), source_capabilities_dir)

    export_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--out",
            str(export_out),
            "--capabilities-dir",
            str(source_capabilities_dir),
        ],
    )

    assert export_result.exit_code == 0
    exported = CapabilityExportOutput.model_validate_json(export_result.stdout)
    archive_path = Path(exported.package_path)
    assert exported.bundle_format == "archive"
    assert archive_path.name == "repo_issue_triage-hermes.omfcap.tar.gz"
    assert archive_path.exists()
    assert Path(exported.unpacked_path or "").joinpath("package.yaml").exists()
    assert Path(exported.unpacked_path or "").joinpath("MANIFEST.sha256").exists()

    verify_result = CliRunner().invoke(app, ["verify", "package", str(archive_path)])
    assert verify_result.exit_code == 0

    import_result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(archive_path),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--available-tool",
            "shell",
            "--validate",
            "--capabilities-dir",
            str(target_capabilities_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--import-dir",
            str(tmp_path / "imports"),
        ],
    )

    assert import_result.exit_code == 0
    imported = CapabilityImportOutput.model_validate_json(import_result.stdout)
    assert imported.package_path == str(archive_path)
    assert imported.unpacked_path is not None
    assert Path(imported.unpacked_path).joinpath("capability.yaml").exists()
    assert Path(imported.imported_package_path).joinpath("capability.yaml").exists()
    assert any(
        "omf inspect import repo_issue_triage" in command
        for command in imported.next_commands
    )


def test_capability_import_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.omfcap.tar.gz"
    payload = b"bad"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("../capability.yaml")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(archive_path),
            "--runtime",
            "generic",
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--import-dir",
            str(tmp_path / "imports"),
        ],
    )

    assert result.exit_code == 1
    assert "unsafe archive member path" in result.stderr


@pytest.mark.parametrize(
    ("target", "expected_files"),
    [
        (
            "codex",
            (
                ".agents/skills/repo_issue_triage/SKILL.md",
                ".agents/skills/repo_issue_triage/references/context.policy.md",
                ".agents/skills/repo_issue_triage/references/harness.md",
                ".agents/skills/repo_issue_triage/references/task_contract.yaml",
                ".agents/skills/repo_issue_triage/references/artifacts.yaml",
                ".agents/skills/repo_issue_triage/references/validation.md",
            ),
        ),
        (
            "claude_code",
            (
                ".claude/skills/repo_issue_triage/SKILL.md",
                ".claude/skills/repo_issue_triage/references/checks.md",
                ".claude/skills/repo_issue_triage/references/task_contract.yaml",
                ".claude/skills/repo_issue_triage/references/artifacts.yaml",
                ".claude/skills/repo_issue_triage/references/validation.md",
            ),
        ),
        (
            "hermes",
            (
                "skills/repo_issue_triage/SKILL.md",
                "skills/repo_issue_triage/references/harness.md",
                "skills/repo_issue_triage/references/context.policy.md",
                "skills/repo_issue_triage/references/task_contract.yaml",
                "skills/repo_issue_triage/references/artifacts.yaml",
                "skills/repo_issue_triage/references/validation.md",
            ),
        ),
        (
            "pi",
            (
                ".pi/skills/repo_issue_triage/SKILL.md",
                ".pi/skills/repo_issue_triage/references/context.policy.md",
                ".pi/skills/repo_issue_triage/references/harness.md",
                ".pi/skills/repo_issue_triage/references/task_contract.yaml",
                ".pi/skills/repo_issue_triage/references/artifacts.yaml",
                ".pi/skills/repo_issue_triage/references/validation.md",
                "package.json",
            ),
        ),
        (
            "odysseus",
            (
                "data/skills/omf/repo_issue_triage/SKILL.md",
                "data/skills/omf/repo_issue_triage/references/harness.md",
                "data/skills/omf/repo_issue_triage/references/task_contract.yaml",
                "data/skills/omf/repo_issue_triage/references/artifacts.yaml",
                "data/skills/omf/repo_issue_triage/references/validation.md",
            ),
        ),
        (
            "generic",
            (
                "skill.md",
                "context.policy.yaml",
                "harness.yaml",
                "eval_set.yaml",
                "contracts/task_contract.yaml",
                "contracts/artifacts.yaml",
                "contracts/validation.md",
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
    skill_candidates = (
        runtime_dir / ".agents" / "skills" / "repo_issue_triage" / "SKILL.md",
        runtime_dir / ".claude" / "skills" / "repo_issue_triage" / "SKILL.md",
        runtime_dir / "skills" / "repo_issue_triage" / "SKILL.md",
        runtime_dir / ".pi" / "skills" / "repo_issue_triage" / "SKILL.md",
        runtime_dir / "data" / "skills" / "omf" / "repo_issue_triage" / "SKILL.md",
        runtime_dir / "skill.md",
    )
    skill_path = next(path for path in skill_candidates if path.exists())
    skill_text = skill_path.read_text(encoding="utf-8")
    assert "omf capability import <package.omfcap.tar.gz>" in skill_text


def test_capability_export_includes_evidence_proof_pack(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), capabilities_dir)
    write_evidence(make_evidence(), evidence_dir)

    full_dir = tmp_path / "exports" / "full"
    full_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--include-evidence",
            "full",
            "--out",
            str(full_dir),
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert full_result.exit_code == 0
    full_output = CapabilityExportOutput.model_validate_json(full_result.stdout)
    assert full_output.evidence_mode == "full"
    assert full_output.evidence_proof_count == 1
    provenance = full_dir / "provenance"
    snapshot = provenance / "source_evidence" / "20260602T010203Z-deadbeef.json"
    snapshot_data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert snapshot_data["files"][0]["content"] == "API_KEY=supersecret\nrun log\n"
    assert (
        provenance / "source_evidence_summaries" / "20260602T010203Z-deadbeef.md"
    ).exists()
    integrity = yaml.safe_load((provenance / "integrity.yaml").read_text("utf-8"))
    assert integrity["evidence"][0]["evidence_id"] == "20260602T010203Z-deadbeef"
    assert integrity["evidence"][0]["integrity_verified"]
    proofs = yaml.safe_load((provenance / "evidence_proofs.yaml").read_text("utf-8"))
    assert proofs["mode"] == "full"
    assert proofs["proofs"][0]["available"]
    assert (
        proofs["proofs"][0]["snapshot_path"]
        == "source_evidence/20260602T010203Z-deadbeef.json"
    )


def test_capability_export_redacts_and_omits_evidence(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), capabilities_dir)
    write_evidence(make_evidence(), evidence_dir)

    redacted_dir = tmp_path / "exports" / "redacted"
    redacted_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--include-evidence",
            "redacted",
            "--out",
            str(redacted_dir),
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    none_dir = tmp_path / "exports" / "none"
    none_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--include-evidence",
            "none",
            "--out",
            str(none_dir),
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert redacted_result.exit_code == 0
    redacted_provenance = redacted_dir / "provenance"
    redacted_snapshot = (
        redacted_provenance / "source_evidence" / "20260602T010203Z-deadbeef.json"
    )
    redacted_text = redacted_snapshot.read_text(encoding="utf-8")
    assert json.loads(redacted_text)["files"][0]["content"] == "[REDACTED]"
    assert "supersecret" not in redacted_text
    assert (redacted_provenance / "redactions.yaml").exists()

    assert none_result.exit_code == 0
    none_output = CapabilityExportOutput.model_validate_json(none_result.stdout)
    none_provenance = none_dir / "provenance"
    assert none_output.evidence_proof_count == 0
    assert (none_provenance / "integrity.yaml").exists()
    assert not (none_provenance / "source_evidence").exists()
    assert not (none_provenance / "evidence_proofs.yaml").exists()


def test_capability_validate_marks_validated_after_passing_target_run(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    command_cwd = tmp_path / "target-run"
    _write_expected_artifact(command_cwd)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-command",
            "true",
            "--command-cwd",
            str(command_cwd),
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "validated"
    assert output.tool_compatibility == "pass"
    assert output.portability_readiness_score == 1.0
    assert output.target_run_executed
    assert output.target_run_exit_code == 0
    assert not output.manual_run_required
    assert output.failure_evidence_id is None
    overlay = yaml.safe_load(Path(output.overlay_path).read_text(encoding="utf-8"))
    assert overlay["status"] == "validated"


def test_capability_validate_marks_validated_after_passing_argv_run(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    command_cwd = tmp_path / "target-run"
    _write_expected_artifact(command_cwd)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-argv",
            "true",
            "--command-cwd",
            str(command_cwd),
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "validated"
    assert output.target_run_executed
    assert output.target_run_exit_code == 0
    assert not output.manual_run_required


def test_capability_validate_rejects_run_command_and_argv_together(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--run-command",
            "true",
            "--run-argv",
            "true",
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code == 1
    assert "mutually exclusive" in result.stderr


def test_capability_validate_static_only_needs_real_run(tmp_path: Path) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "needs_validation"
    assert not output.target_run_executed
    assert output.manual_run_required
    # Pending must carry a real reason and a runnable suggestion, never the old
    # unfillable placeholder, so an agent does not chase a phantom failure.
    assert output.manual_run_reason is not None
    assert all("<target-agent-run>" not in command for command in output.next_commands)
    assert any(
        "codex exec --full-auto < task.md" in command and "--run-command" in command
        for command in output.next_commands
    )


def test_capability_import_next_commands_suggest_runnable_validate(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    # The final suggested command must be able to reach `validated`: it carries a
    # real --run-command suggestion, not the bare validate that dead-ends at
    # needs_validation, and never the old unfillable placeholder.
    assert all("<target-agent-run>" not in command for command in output.next_commands)
    assert any(
        "--run-command" in command and "codex exec --full-auto < task.md" in command
        for command in output.next_commands
    )


def test_mcp_tools_cover_full_port_lifecycle(tmp_path: Path) -> None:
    names = {tool["name"] for tool in mcp_tool_definitions()}
    assert {
        "omf_import_capability",
        "omf_remap_capability",
        "omf_adapt_capability",
        "omf_explain",
        "omf_card",
    } <= names

    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)

    exported = dispatch_tool(
        "omf_export_capability",
        {
            "capability_name": "repo_issue_triage",
            "target": "codex",
            "target_model": "gpt-5.5",
            "out": str(export_dir),
            "capabilities_dir": str(source_caps),
            "evidence_dir": str(evidence_dir),
        },
    )

    imported = dispatch_tool(
        "omf_import_capability",
        {
            "bundle_path": str(exported["export_path"]),
            "runtime": "codex",
            "model": "gpt-5.5",
            "available_tools": ["shell"],
            "capabilities_dir": str(target_caps),
            "eval_dir": str(eval_dir),
            "evidence_dir": str(evidence_dir),
            "import_dir": str(tmp_path / "imports"),
        },
    )
    assert imported["capability_name"] == "repo_issue_triage"

    validated = dispatch_tool(
        "omf_validate_capability",
        {
            "capability_name": "repo_issue_triage",
            "target": "codex",
            "model": "gpt-5.5",
            "available_tools": ["shell"],
            "capabilities_dir": str(target_caps),
            "eval_dir": str(eval_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    # MCP validation is record-only: it never executes a target run, so it stays
    # pending and routes the agent to the risk-gated CLI run-command path.
    assert validated["status"] == "needs_validation"
    assert validated["manual_run_required"] is True
    next_commands = cast("tuple[str, ...]", validated["next_commands"])
    assert any("--run-command" in command for command in next_commands)

    card = dispatch_tool(
        "omf_card",
        {
            "capability_name": "repo_issue_triage",
            "capabilities_dir": str(target_caps),
        },
    )
    assert card["capability_name"] == "repo_issue_triage"
    assert card["content"]


def test_capability_validate_missing_expected_artifact_needs_adaptation(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    command_cwd = tmp_path / "target-run"
    command_cwd.mkdir()
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-command",
            "true",
            "--command-cwd",
            str(command_cwd),
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "needs_adaptation"
    assert output.failure_evidence_id is not None
    report = yaml.safe_load(
        Path(output.validation_report_path).read_text(encoding="utf-8"),
    )
    blocker_names = {blocker["name"] for blocker in report["hard_blockers"]}
    assert blocker_names == {"missing_artifact"}
    assert report["target_run"]["executed"]
    eval_result = yaml.safe_load(
        Path(output.eval_path or "").read_text(encoding="utf-8"),
    )
    checks = {check["name"]: check for check in eval_result["checks"]}
    assert checks["artifact_exists:output/report.json"]["status"] == "fail"
    assert checks["portability_readiness"]["status"] == "pass"


def test_capability_validate_contract_validator_adds_confidence(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    package_dir = target_caps / "repo_issue_triage"
    command_cwd = tmp_path / "target-run"
    _write_expected_artifact(command_cwd)
    assert not package_dir.joinpath("output", "report.json").exists()

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-command",
            "true",
            "--command-cwd",
            str(command_cwd),
            "--run-contract-validator",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "validated"
    report = yaml.safe_load(
        Path(output.validation_report_path).read_text(encoding="utf-8"),
    )
    assert report["validation_confidence"]["score"] == 1.0
    assert report["validation_confidence"]["level"] == "high"
    eval_result = yaml.safe_load(
        Path(output.eval_path or "").read_text(encoding="utf-8"),
    )
    checks = {check["name"]: check for check in eval_result["checks"]}
    assert checks["contract_validator"]["status"] == "pass"


def test_capability_validate_target_run_failure_needs_adaptation(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "codex"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-command",
            "false",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "needs_adaptation"
    assert output.target_run_executed
    assert output.target_run_exit_code == 1
    assert output.failure_evidence_id is not None


def test_capability_validate_records_failure_when_tools_missing(tmp_path: Path) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "hermes"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--available-tool",
            "file_system",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--available-tool",
            "file_system",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "needs_adaptation"
    assert output.tool_compatibility == "partial"
    assert output.failure_evidence_id is not None
    assert Path(output.failure_evidence_path or "").exists()


def test_capability_validate_errors_when_not_imported(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code == 1
    assert "no imported target" in result.stderr


def _run_ok(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.stdout


def test_runtime_export_assets_have_native_sections(tmp_path: Path) -> None:
    caps = tmp_path / "capabilities"
    write_manifest(make_manifest(), caps)
    hermes_dir = tmp_path / "exports" / "hermes"
    codex_dir = tmp_path / "exports" / "codex"
    pi_dir = tmp_path / "exports" / "pi"
    odysseus_dir = tmp_path / "exports" / "odysseus"
    generic_dir = tmp_path / "exports" / "generic"
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--skill-style",
            "full",
            "--out",
            str(hermes_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--skill-style",
            "full",
            "--out",
            str(codex_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "pi",
            "--target-model",
            "local",
            "--skill-style",
            "full",
            "--out",
            str(pi_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "odysseus",
            "--target-model",
            "local",
            "--skill-style",
            "full",
            "--out",
            str(odysseus_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "generic",
            "--target-model",
            "local",
            "--skill-style",
            "full",
            "--out",
            str(generic_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )

    skill = (
        hermes_dir / "runtime" / "hermes" / "skills" / "repo_issue_triage" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: repo_issue_triage" in skill
    assert "## Trigger" in skill
    assert "## Context Policy" in skill
    assert "## Procedure" in skill
    assert "## Completion Criteria" in skill
    assert "schema_valid" in skill
    assert ".env" in skill

    codex_skill = (
        codex_dir
        / "runtime"
        / "codex"
        / ".agents"
        / "skills"
        / "repo_issue_triage"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: repo_issue_triage" in codex_skill
    assert "## Trigger" in codex_skill
    assert "schema_valid" in codex_skill

    pi_skill = (
        pi_dir / "runtime" / "pi" / ".pi" / "skills" / "repo_issue_triage" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: repo_issue_triage" in pi_skill
    assert "## Trigger" in pi_skill
    assert "schema_valid" in pi_skill

    odysseus_skill = (
        odysseus_dir
        / "runtime"
        / "odysseus"
        / "data"
        / "skills"
        / "omf"
        / "repo_issue_triage"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: repo_issue_triage" in odysseus_skill
    assert "category: omf" in odysseus_skill
    assert "## When to Use" in odysseus_skill
    assert "schema_valid" in odysseus_skill

    generic_skill = (generic_dir / "runtime" / "generic" / "skill.md").read_text(
        encoding="utf-8"
    )
    assert "## Trigger" in generic_skill
    assert "## Completion Criteria" in generic_skill


def _seed_hermes_bundle(source_caps: Path, export_dir: Path) -> None:
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )


def test_capability_import_fails_on_existing_by_default(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    _seed_hermes_bundle(source_caps, export_dir)
    import_args = [
        "capability",
        "import",
        str(export_dir),
        "--runtime",
        "hermes",
        "--model",
        "qwen3.6-27b",
        "--capabilities-dir",
        str(target_caps),
        "--eval-dir",
        str(tmp_path / "evals"),
        "--evidence-dir",
        str(tmp_path / "evidence"),
    ]
    _run_ok(import_args)

    second = CliRunner().invoke(app, import_args)

    assert second.exit_code == 1
    assert "already exists" in second.stderr


def test_capability_import_versions_on_collision(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    _seed_hermes_bundle(source_caps, export_dir)
    import_args = [
        "capability",
        "import",
        str(export_dir),
        "--runtime",
        "hermes",
        "--model",
        "qwen3.6-27b",
        "--capabilities-dir",
        str(target_caps),
        "--eval-dir",
        str(tmp_path / "evals"),
        "--evidence-dir",
        str(tmp_path / "evidence"),
    ]
    _run_ok(import_args)

    result = CliRunner().invoke(app, [*import_args, "--if-exists", "version"])

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    assert output.capability_name == "repo_issue_triage_v2"
    assert Path(output.imported_package_path).name == "repo_issue_triage_v2"
    assert (target_caps / "repo_issue_triage" / "capability.yaml").exists()
    assert (target_caps / "repo_issue_triage_v2" / "capability.yaml").exists()


def test_capability_import_overwrite_allows_reimport(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    _seed_hermes_bundle(source_caps, export_dir)
    import_args = [
        "capability",
        "import",
        str(export_dir),
        "--runtime",
        "hermes",
        "--model",
        "qwen3.6-27b",
        "--capabilities-dir",
        str(target_caps),
        "--eval-dir",
        str(tmp_path / "evals"),
        "--evidence-dir",
        str(tmp_path / "evidence"),
    ]
    _run_ok(import_args)

    result = CliRunner().invoke(app, [*import_args, "--if-exists", "overwrite"])

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    assert output.capability_name == "repo_issue_triage"
    assert (target_caps / "repo_issue_triage" / "capability.yaml").exists()


def test_capability_import_as_and_namespace(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    _seed_hermes_bundle(source_caps, export_dir)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--as",
            "repo_issue_triage_hermes",
            "--namespace",
            "imported",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    assert output.capability_name == "repo_issue_triage_hermes"
    package = target_caps / "imported" / "repo_issue_triage_hermes"
    assert package.joinpath("capability.yaml").exists()
    imported = load_manifest("repo_issue_triage_hermes", target_caps / "imported")
    assert imported.name == "repo_issue_triage_hermes"


def test_harden_connects_target_validation_failure(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    _seed_hermes_bundle(source_caps, export_dir)
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--available-tool",
            "file_system",
            "--validate",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "harden",
            "repo_issue_triage",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
        ],
    )

    assert result.exit_code == 0
    output = HardenOutput.model_validate_json(result.stdout)
    assert any(
        "omf capability validate repo_issue_triage" in action
        for action in output.recommended_actions
    )
    assert any("omf learn" in action for action in output.recommended_actions)


def _seed_project_transfer_import(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--source-project",
            "source-repo",
            "--target-project",
            "target-repo",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    return target_caps, eval_dir, evidence_dir


def test_capability_remap_writes_plan(tmp_path: Path) -> None:
    target_caps, _, _ = _seed_project_transfer_import(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "remap",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--map",
            "repository_path=/target",
            "--map",
            "test_command=pytest",
            "--capabilities-dir",
            str(target_caps),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityRemapOutput.model_validate_json(result.stdout)
    assert output.binding_count == 2
    assert output.complete
    plan = yaml.safe_load(Path(output.remap_path).read_text(encoding="utf-8"))
    assert {binding["key"] for binding in plan["bindings"]} == {
        "repository_path",
        "test_command",
    }


def test_capability_remap_resolves_context_for_validation(tmp_path: Path) -> None:
    target_caps, eval_dir, evidence_dir = _seed_project_transfer_import(tmp_path)
    command_cwd = tmp_path / "target-run"
    _write_expected_artifact(command_cwd)
    validate_args = [
        "capability",
        "validate",
        "repo_issue_triage",
        "--target",
        "codex",
        "--model",
        "gpt-5.5",
        "--available-tool",
        "shell",
        "--run-command",
        "true",
        "--command-cwd",
        str(command_cwd),
        "--capabilities-dir",
        str(target_caps),
        "--eval-dir",
        str(eval_dir),
        "--evidence-dir",
        str(evidence_dir),
    ]

    before = CliRunner().invoke(app, validate_args)
    assert before.exit_code == 0
    assert (
        CapabilityValidateOutput.model_validate_json(before.stdout).status
        == "needs_adaptation"
    )

    _run_ok(
        [
            "capability",
            "remap",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--map",
            "repository_path=/target",
            "--capabilities-dir",
            str(target_caps),
        ],
    )

    after = CliRunner().invoke(app, validate_args)
    assert after.exit_code == 0
    assert (
        CapabilityValidateOutput.model_validate_json(after.stdout).status == "validated"
    )


def test_low_readiness_risk_does_not_block_validated_target_run(
    tmp_path: Path,
) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    command_cwd = tmp_path / "target-run"
    _write_expected_artifact(command_cwd)
    write_manifest(make_manifest(), source_caps)
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "generic",
            "--target-model",
            "small-local",
            "--source-project",
            "source-repo",
            "--target-project",
            "target-repo",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "generic",
            "--model",
            "small-local",
            "--available-tool",
            "shell",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    _run_ok(
        [
            "capability",
            "remap",
            "repo_issue_triage",
            "--target",
            "generic",
            "--model",
            "small-local",
            "--map",
            "repository_path=/target",
            "--capabilities-dir",
            str(target_caps),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "generic",
            "--model",
            "small-local",
            "--available-tool",
            "shell",
            "--run-command",
            "true",
            "--command-cwd",
            str(command_cwd),
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityValidateOutput.model_validate_json(result.stdout)
    assert output.status == "validated"
    assert output.portability_readiness_score == 0.65
    report = yaml.safe_load(
        Path(output.validation_report_path).read_text(encoding="utf-8"),
    )
    assert report["hard_blockers"] == []
    assert report["portability_risk"]["advisory_only"] is True
    assert report["validation_confidence"]["level"] == "medium"


def test_validation_report_compares_eval_pass_rate(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    metrics = PromotionMetrics(
        evidence_count=4,
        successful_evidence_count=3,
        failed_evidence_count=1,
        harness_pass_rate=0.9,
        human_intervention_rate=0.1,
        retry_rate=0.0,
        eval_pass_rate=0.8,
    )
    write_manifest(
        make_manifest().model_copy(update={"promotion_metrics": metrics}),
        source_caps,
    )
    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "codex",
            "--target-model",
            "gpt-5.5",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--validate",
            "--capabilities-dir",
            str(target_caps),
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
    comparison = report["pass_rate_comparison"]
    assert comparison["source_pass_rate"] == 0.8
    assert comparison["target_pass_rate"] == 1.0
    assert comparison["delta"] == 0.2


def test_capability_adapt_updates_and_persists_overrides(tmp_path: Path) -> None:
    target_caps, eval_dir, evidence_dir = _seed_project_transfer_import(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "adapt",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--instruction-variant",
            "compact",
            "--context-variant",
            "compressed",
            "--require-human-review",
            "--capabilities-dir",
            str(target_caps),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityAdaptOutput.model_validate_json(result.stdout)
    assert output.instruction_variant == "compact"
    assert output.context_variant == "compressed"
    assert output.required_human_review
    target_dir = Path(output.overlay_path).parent
    instructions = (target_dir / "instructions.md").read_text(encoding="utf-8")
    assert "compact" in instructions.lower()
    assert "Compressed Context Pack" in (target_dir / "context.pack.md").read_text(
        encoding="utf-8"
    )

    # A subsequent validate preserves the adapted overrides instead of
    # recomputing them.
    _run_ok(
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            "--available-tool",
            "shell",
            "--run-command",
            "true",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    overlay = yaml.safe_load(Path(output.overlay_path).read_text(encoding="utf-8"))
    assert overlay["overrides"]["instruction_variant"] == "compact"
    assert overlay["overrides"]["context_variant"] == "compressed"
    assert overlay["overrides"]["required_human_review"] is True


def test_model_profile_marks_downgrade(tmp_path: Path) -> None:
    source_caps = tmp_path / "src"
    target_caps = tmp_path / "tgt"
    export_dir = tmp_path / "bundle"
    _seed_hermes_bundle(source_caps, export_dir)

    result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--available-tool",
            "file_system",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code == 0
    output = CapabilityImportOutput.model_validate_json(result.stdout)
    report = yaml.safe_load(
        Path(output.validation_report_path).read_text(encoding="utf-8"),
    )
    delta = report["model_delta"]
    assert delta["downgrade"]
    assert delta["source_profile"]["model_class"] == "frontier"
    assert delta["target_profile"]["model_class"] == "local"
    assert delta["target_profile"]["context_tokens"] == 32768


class HealthEntriesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str | None = None
    count: int
    entries: list[dict[str, object]]


def test_health_and_card_reflect_export_and_import_status(tmp_path: Path) -> None:
    source_caps = tmp_path / "source-capabilities"
    target_caps = tmp_path / "target-capabilities"
    export_dir = tmp_path / "exports" / "repo_issue_triage-hermes"
    eval_dir = tmp_path / "evals"
    evidence_dir = tmp_path / "evidence"
    write_manifest(make_manifest(), source_caps)

    export_result = CliRunner().invoke(
        app,
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(source_caps),
        ],
    )
    assert export_result.exit_code == 0
    source_entry = _health_entry(source_caps, eval_dir)
    assert source_entry["export_status"] == "exported"
    assert source_entry["export_count"] == 1
    assert source_entry["import_status"] == "not_imported"

    import_result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
            "--project",
            "target-repo",
            "--available-tool",
            "file_system",
            "--validate",
            "--capabilities-dir",
            str(target_caps),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    assert import_result.exit_code == 0
    target_entry = _health_entry(target_caps, eval_dir)
    assert target_entry["import_status"] == "imported"
    assert target_entry["import_count"] == 1
    assert target_entry["validation_status"] == "needs_adaptation"
    assert target_entry["target_validation_count"] == 1

    card_result = CliRunner().invoke(
        app,
        [
            "card",
            "repo_issue_triage",
            "--write",
            "--capabilities-dir",
            str(target_caps),
        ],
    )
    assert card_result.exit_code == 0
    card = (target_caps / "repo_issue_triage" / "README.md").read_text(encoding="utf-8")
    assert "Import status: imported" in card
    assert "hermes:qwen3.6-27b" in card


def _health_entry(capabilities_dir: Path, eval_dir: Path) -> dict[str, object]:
    result = CliRunner().invoke(
        app,
        [
            "health",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
            "--eval-dir",
            str(eval_dir),
        ],
    )
    assert result.exit_code == 0
    output = HealthEntriesOutput.model_validate_json(result.stdout)
    assert len(output.entries) == 1
    return output.entries[0]


def make_evidence() -> EvidenceRecord:
    content = "API_KEY=supersecret\nrun log\n"
    raw = content.encode("utf-8")
    record = EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        normalized_goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5", tools=("shell",)),
        files=(
            CapturedTextFile(
                role="command_output",
                path="run.log",
                content=content,
                size_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
            ),
        ),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        success_or_failure_label="success",
    )
    return append_integrity_link(
        record,
        artifact_type="evidence",
        artifact_id=record.id,
    )


def _write_expected_artifact(root: Path) -> None:
    artifact = root / "output" / "report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}", encoding="utf-8")


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
            required_inputs=("AGENTS.md",),
            expected_artifacts=("output/report.json",),
            validation_checks=("artifact_exists:output/report.json",),
        ),
        record_quality=RecordQuality(score=1.0, strict_ready=True),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def test_capability_export_launcher_skill_omits_goal_by_default(
    tmp_path: Path,
) -> None:
    caps = tmp_path / "capabilities"
    export_dir = tmp_path / "exports" / "hermes-launcher"
    write_manifest(make_manifest(), caps)

    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )

    portability = yaml.safe_load(
        (export_dir / "portability.yaml").read_text(encoding="utf-8"),
    )
    assert portability["lifecycle_owner"] == "omf"
    assert portability["agent_view"]["skill_style"] == "launcher"
    assert not portability["agent_view"]["direct_execution_allowed"]
    skill = (
        export_dir / "runtime" / "hermes" / "skills" / "repo_issue_triage" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "omf_managed: true" in skill
    assert "omf_schema: omf.runtime_skill.v0.1" in skill
    assert "execution_mode: omf_managed" in skill
    assert "direct_execution_allowed: false" in skill
    assert "# OMF Capability Launcher: repo_issue_triage" in skill
    assert "omf capability import <package.omfcap.tar.gz> --runtime hermes" in skill
    assert "omf card repo_issue_triage" in skill
    assert "omf capability validate repo_issue_triage --target hermes" in skill
    assert "Do not execute the capability goal directly" in skill
    # The goal stays in the OMF package; the launcher must not restate it.
    assert "triage repo issue" not in skill
    assert "## Procedure" not in skill
    references = (
        export_dir / "runtime" / "hermes" / "skills" / "repo_issue_triage"
    ) / "references"
    assert not references.joinpath("capability.md").exists()
    assert references.joinpath("harness.md").exists()


def test_capability_export_full_skill_style_keeps_instruction_projection(
    tmp_path: Path,
) -> None:
    caps = tmp_path / "capabilities"
    export_dir = tmp_path / "exports" / "hermes-full"
    write_manifest(make_manifest(), caps)

    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "hermes",
            "--target-model",
            "qwen3.6-27b",
            "--skill-style",
            "full",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )

    portability = yaml.safe_load(
        (export_dir / "portability.yaml").read_text(encoding="utf-8"),
    )
    assert portability["agent_view"]["skill_style"] == "full"
    assert portability["agent_view"]["direct_execution_allowed"]
    skill_dir = export_dir / "runtime" / "hermes" / "skills" / "repo_issue_triage"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "## Trigger" in skill
    assert "triage repo issue" in skill
    assert "omf_managed" not in skill
    assert skill_dir.joinpath("references", "capability.md").exists()


def test_capability_export_launcher_skill_for_odysseus_keeps_frontmatter(
    tmp_path: Path,
) -> None:
    caps = tmp_path / "capabilities"
    export_dir = tmp_path / "exports" / "odysseus-launcher"
    write_manifest(make_manifest(), caps)

    _run_ok(
        [
            "capability",
            "export",
            "repo_issue_triage",
            "--target",
            "odysseus",
            "--target-model",
            "local",
            "--out",
            str(export_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )

    skill = (
        export_dir
        / "runtime"
        / "odysseus"
        / "data"
        / "skills"
        / "omf"
        / "repo_issue_triage"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "omf_managed: true" in skill
    assert "category: omf" in skill
    assert "status: published" in skill
    assert "# OMF Capability Launcher: repo_issue_triage" in skill
    assert "omf capability import <package.omfcap.tar.gz> --runtime odysseus" in skill
    assert "triage repo issue" not in skill
