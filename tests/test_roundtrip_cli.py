"""End-to-end product loop: import-run -> promote -> export -> import -> validate."""

import json
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.storage import load_manifest

AVAILABLE_TOOL_ARGS = (
    "--available-tool",
    "external_agent_log",
    "--available-tool",
    "importer:codex",
    "--available-tool",
    "file_system",
)


def test_full_capability_roundtrip_reaches_validated_target(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    export_dir = tmp_path / "exports" / "codex"
    target_capabilities_dir = tmp_path / "target-capabilities"
    eval_dir = tmp_path / "evals"
    target_evidence_dir = tmp_path / "target-evidence"
    log_path.write_text(
        "Codex completed the task.\nAll tests passed.\n",
        encoding="utf-8",
    )

    imported = _run_ok(
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "triage repo issue",
            "--model",
            "gpt-5.5",
            "--outcome",
            "success",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    promoted = _run_ok(
        [
            "promote",
            imported["evidence_id"],
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
    exported = _run_ok(
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
            str(capabilities_dir),
        ],
    )
    re_imported = _run_ok(
        [
            "capability",
            "import",
            str(export_dir),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            *AVAILABLE_TOOL_ARGS,
            "--capabilities-dir",
            str(target_capabilities_dir),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(target_evidence_dir),
        ],
    )
    validated = _run_ok(
        [
            "capability",
            "validate",
            "repo_issue_triage",
            "--target",
            "codex",
            "--model",
            "gpt-5.5",
            *AVAILABLE_TOOL_ARGS,
            "--run-command",
            "true",
            "--capabilities-dir",
            str(target_capabilities_dir),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(target_evidence_dir),
        ],
    )

    assert promoted["status"] == "candidate"
    assert exported["target_runtime"] == "codex"
    assert export_dir.joinpath("capability.yaml").exists()
    assert re_imported["tool_compatibility"] == "pass"
    assert validated["status"] == "validated"
    assert validated["portability_readiness_score"] == 1.0
    assert validated["target_run_executed"]
    assert validated["target_run_exit_code"] == 0
    assert validated["failure_evidence_id"] is None
    source_manifest = load_manifest("repo_issue_triage", capabilities_dir)
    target_manifest = load_manifest("repo_issue_triage", target_capabilities_dir)
    assert source_manifest.source_evidence_ids == (imported["evidence_id"],)
    assert target_manifest.name == source_manifest.name
    assert target_manifest.runtime.tools == source_manifest.runtime.tools


def _run_ok(args: list[str]) -> dict[str, Any]:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return cast("dict[str, Any]", json.loads(result.stdout))
