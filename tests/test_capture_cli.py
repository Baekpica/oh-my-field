from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.storage import load_evidence


class CaptureOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    evidence_path: str
    harness_status: str


def test_capture_creates_evidence_file_from_manual_inputs(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.md"
    output_path = tmp_path / "output.txt"
    test_path = tmp_path / "pytest.txt"
    evidence_dir = tmp_path / "evidence"
    prompt_path.write_text("Find the bug.", encoding="utf-8")
    output_path.write_text("Fixed parser branch.", encoding="utf-8")
    test_path.write_text("1 passed", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "triage repo issue",
            "--prompt",
            str(prompt_path),
            "--command-output",
            str(output_path),
            "--test-result",
            str(test_path),
            "--feedback",
            "looks reusable",
            "--model",
            "gpt-5.5",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence_path = Path(output.evidence_path)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence_path.exists()
    assert evidence.goal == "triage repo issue"
    assert evidence.runtime.name == "codex"
    assert evidence.runtime.model == "gpt-5.5"
    assert evidence.harness.status == output.harness_status
    assert [captured.role for captured in evidence.files] == [
        "prompt",
        "command_output",
        "test_result",
    ]


def test_capture_fails_for_missing_file_path(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "triage repo issue",
            "--prompt",
            str(tmp_path / "missing.md"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
        ],
    )

    assert result.exit_code != 0
    assert "could not read input file" in result.stderr


def test_capture_executes_shell_command_and_stores_structured_result(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "run smoke command",
            "--command",
            "printf hello",
            "--command-cwd",
            str(tmp_path),
            "--runtime-tool",
            "shell",
            "--outcome",
            "success",
            "--improvement-note",
            "keep command outputs for replay",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence.generated_commands == ("printf hello",)
    assert evidence.command_executions[0].stdout == "hello"
    assert evidence.command_executions[0].exit_code == 0
    assert evidence.runtime.tools == ("shell",)
    assert evidence.success_or_failure_label == "success"
    assert evidence.improvement_notes == ("keep command outputs for replay",)


def test_capture_preserves_failed_command_as_failed_evidence(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "capture failed run",
            "--command",
            "sh -c 'echo failed >&2; exit 7'",
            "--command-cwd",
            str(tmp_path),
            "--outcome",
            "failure",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert output.harness_status == "fail"
    assert evidence.command_executions[0].exit_code == 7
    assert evidence.errors == ("failed\n",)
