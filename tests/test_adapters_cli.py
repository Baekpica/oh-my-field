from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.storage import load_evidence


class AgentImportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    evidence_path: str
    adapter: str
    artifact_count: int
    warnings: tuple[str, ...]


def test_import_run_captures_external_agent_log_and_artifacts(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "codex.log"
    diff_path = tmp_path / "change.diff"
    test_path = tmp_path / "pytest.txt"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("Codex completed a long run.", encoding="utf-8")
    diff_path.write_text("diff --git a/app.py b/app.py", encoding="utf-8")
    test_path.write_text("1 passed", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture external agent run",
            "--diff",
            str(diff_path),
            "--test-result",
            str(test_path),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert output.adapter == "codex"
    assert output.artifact_count == 3
    assert evidence.runtime.name == "codex"
    assert evidence.runtime.tools == ("external_agent_log", "importer:codex")
    assert [file.role for file in evidence.files] == [
        "artifact",
        "diff",
        "test_result",
    ]
    assert evidence.tool_calls[0].tool == "agent_importer.import_run"
    assert evidence.capture_status == "captured"
    assert evidence.task_outcome == "unknown"
    assert evidence.success_or_failure_label == "unknown"
    assert evidence.integrity_chain[-1].artifact_type == "evidence"


def test_import_run_redacts_secrets(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text(
        "API_KEY=supersecret\nAuthorization: Bearer abc123xyz\nrun ok\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture external agent run",
            "--redact-secrets",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    log_file = evidence.files[0]
    assert log_file.redacted
    assert log_file.storage_mode == "inline"
    assert "supersecret" not in log_file.content
    assert "abc123xyz" not in log_file.content
    assert "[REDACTED]" in log_file.content


def test_import_run_externalizes_binary_artifact(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    binary_path = tmp_path / "image.png"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("run ok", encoding="utf-8")
    binary_path.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x01")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture external agent run",
            "--artifact",
            str(binary_path),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    binary_file = next(f for f in evidence.files if f.path.endswith("image.png"))
    assert binary_file.storage_mode == "external"
    assert binary_file.content == ""
    assert binary_file.size_bytes > 0
    assert binary_file.mime_type == "image/png"


def test_import_run_externalizes_large_artifact(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    big_path = tmp_path / "big.txt"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("run ok", encoding="utf-8")
    big_path.write_text("x" * 5000, encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture external agent run",
            "--artifact",
            str(big_path),
            "--max-artifact-bytes",
            "1024",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    big_file = next(f for f in evidence.files if f.path.endswith("big.txt"))
    assert big_file.storage_mode == "external"
    assert big_file.content == ""
    assert big_file.size_bytes == 5000


def test_import_run_discovers_agent_artifact_root_roles(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "claude-code.log"
    artifact_root = tmp_path / "agent-artifacts"
    evidence_dir = tmp_path / "evidence"
    artifact_root.mkdir()
    log_path.write_text("Claude Code finished.", encoding="utf-8")
    artifact_root.joinpath("changes.patch").write_text("diff", encoding="utf-8")
    artifact_root.joinpath("pytest-output.txt").write_text("1 passed", encoding="utf-8")
    artifact_root.joinpath("stdout.log").write_text("ok", encoding="utf-8")
    artifact_root.joinpath("final.md").write_text("done", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "claude_code",
            "--log",
            str(log_path),
            "--goal",
            "capture external agent run",
            "--artifact-root",
            str(artifact_root),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert output.adapter == "claude_code"
    assert output.artifact_count == 5
    assert [file.role for file in evidence.files] == [
        "artifact",
        "diff",
        "artifact",
        "test_result",
        "command_output",
    ]


def test_import_run_applies_default_artifact_root_excludes(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "codex.log"
    artifact_root = tmp_path / "agent-artifacts"
    evidence_dir = tmp_path / "evidence"
    artifact_root.mkdir()
    log_path.write_text("Codex finished.", encoding="utf-8")
    artifact_root.joinpath("keep.txt").write_text("keep", encoding="utf-8")
    artifact_root.joinpath(".env").write_text("TOKEN=secret", encoding="utf-8")
    artifact_root.joinpath(".git").mkdir()
    artifact_root.joinpath(".git", "config").write_text("secret", encoding="utf-8")
    artifact_root.joinpath(".venv").mkdir()
    artifact_root.joinpath(".venv", "token.txt").write_text("secret", encoding="utf-8")
    artifact_root.joinpath("node_modules").mkdir()
    artifact_root.joinpath("node_modules", "pkg.json").write_text(
        "{}",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture safe artifacts",
            "--artifact-root",
            str(artifact_root),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert output.artifact_count == 2
    assert [Path(file.path).name for file in evidence.files] == [
        "codex.log",
        "keep.txt",
    ]
    assert output.warnings == ()


def test_import_run_warns_for_unbounded_current_directory_artifact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "codex.log"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("Codex finished.", encoding="utf-8")
    tmp_path.joinpath("keep.txt").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture broad artifacts",
            "--artifact-root",
            ".",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    assert output.warnings == (
        "--artifact-root . was used without --max-artifact-count, "
        "--max-total-artifact-bytes, or --redact-secrets; broad imports can "
        "capture unintended local artifacts",
    )


def test_import_run_applies_explicit_excludes_and_omfignore(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "codex.log"
    artifact_root = tmp_path / "agent-artifacts"
    evidence_dir = tmp_path / "evidence"
    ignored_dir = artifact_root / "ignored"
    ignored_dir.mkdir(parents=True)
    log_path.write_text("Codex finished.", encoding="utf-8")
    artifact_root.joinpath(".omfignore").write_text(
        "ignored/**\n*.pem\n", encoding="utf-8"
    )
    artifact_root.joinpath("keep.txt").write_text("keep", encoding="utf-8")
    artifact_root.joinpath("drop.log").write_text("drop", encoding="utf-8")
    artifact_root.joinpath("private.pem").write_text("secret", encoding="utf-8")
    ignored_dir.joinpath("data.txt").write_text("ignored", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture filtered artifacts",
            "--artifact-root",
            str(artifact_root),
            "--exclude",
            "*.log",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert [Path(file.path).name for file in evidence.files] == [
        "codex.log",
        "keep.txt",
    ]


def test_import_run_fails_when_artifact_count_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "codex.log"
    artifact_root = tmp_path / "agent-artifacts"
    artifact_root.mkdir()
    log_path.write_text("Codex finished.", encoding="utf-8")
    artifact_root.joinpath("one.txt").write_text("one", encoding="utf-8")
    artifact_root.joinpath("two.txt").write_text("two", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture limited artifacts",
            "--artifact-root",
            str(artifact_root),
            "--max-artifact-count",
            "1",
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code != 0
    assert "max artifact count exceeded" in result.stderr


def test_import_run_fails_when_total_artifact_bytes_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "codex.log"
    artifact_root = tmp_path / "agent-artifacts"
    artifact_root.mkdir()
    log_path.write_text("Codex finished.", encoding="utf-8")
    artifact_root.joinpath("one.txt").write_text("1234", encoding="utf-8")
    artifact_root.joinpath("two.txt").write_text("5678", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture size-limited artifacts",
            "--artifact-root",
            str(artifact_root),
            "--max-total-artifact-bytes",
            "4",
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code != 0
    assert "max total artifact bytes exceeded" in result.stderr


def test_import_run_skips_symlinks_under_artifact_root(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    artifact_root = tmp_path / "agent-artifacts"
    evidence_dir = tmp_path / "evidence"
    target_path = tmp_path / "outside.txt"
    symlink_path = artifact_root / "linked.txt"
    artifact_root.mkdir()
    log_path.write_text("Codex finished.", encoding="utf-8")
    artifact_root.joinpath("keep.txt").write_text("keep", encoding="utf-8")
    target_path.write_text("outside", encoding="utf-8")
    try:
        symlink_path.symlink_to(target_path)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture no symlink artifacts",
            "--artifact-root",
            str(artifact_root),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert [Path(file.path).name for file in evidence.files] == [
        "codex.log",
        "keep.txt",
    ]


def test_import_run_records_explicit_task_outcome(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("Codex completed the task.", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "capture successful external agent run",
            "--outcome",
            "success",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = AgentImportOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence.capture_status == "captured"
    assert evidence.task_outcome == "success"
    assert evidence.success_or_failure_label == "success"
