import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.integrity import append_integrity_link
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    ContextPolicy,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowControl,
    WorkflowManifest,
)
from oh_my_field.storage import load_manifest, write_evidence, write_manifest


class CapabilityExportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    export_path: str
    portability_path: str
    runtime_export_path: str
    target_runtime: str
    target_model: str | None
    evidence_mode: str
    evidence_proof_count: int


class CapabilityImportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
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


class CapabilityValidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
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
    assert output.portability_readiness_score == 0.45
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
    assert report["readiness"]["score"] == 0.45
    assert report["readiness"]["required_pass_rate"] == 0.8
    factor_names = {factor["name"] for factor in report["readiness"]["factors"]}
    assert factor_names == {
        "cross_runtime",
        "model_transfer",
        "project_transfer",
        "unavailable_tool",
    }
    assert report["model_delta"]["model_changed"]
    assert report["eval_id"] == output.eval_id
    assert report["failure_evidence_id"] == output.failure_evidence_id
    overlay = yaml.safe_load(Path(output.overlay_path).read_text(encoding="utf-8"))
    target_dir = Path(output.overlay_path).parent
    assert overlay["target"]["runtime"] == "generic"
    assert overlay["target"]["model"] == "small-local"
    assert overlay["status"] == "needs_adaptation"
    assert overlay["overrides"]["instruction_variant"] == "compact"
    assert overlay["overrides"]["context_variant"] == "full"
    assert overlay["eval_id"] == output.eval_id
    assert overlay["failure_evidence_id"] == output.failure_evidence_id
    assert target_dir.joinpath("README.md").exists()
    assert target_dir.joinpath("instructions.md").exists()
    assert target_dir.joinpath("context.pack.md").exists()


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
            "generic",
            "--target-model",
            "local",
            "--out",
            str(generic_dir),
            "--capabilities-dir",
            str(caps),
        ],
    )

    skill = (
        hermes_dir / "runtime" / "hermes" / "skills" / "repo_issue_triage.md"
    ).read_text(encoding="utf-8")
    assert "## Trigger" in skill
    assert "## Context Policy" in skill
    assert "## Procedure" in skill
    assert "## Completion Criteria" in skill
    assert "schema_valid" in skill
    assert ".env" in skill

    agents = (codex_dir / "runtime" / "codex" / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Activation" in agents
    assert "## Safety Boundary" in agents
    assert "schema_valid" in agents

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
