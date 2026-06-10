from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.application.capture import (
    CaptureDependencies,
    CaptureFileInput,
    CaptureRequest,
    run_capture_workflow,
)
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
    assert evidence.integrity_chain[-1].artifact_type == "evidence"
    assert evidence.integrity_chain[-1].artifact_id == evidence.id
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
    assert evidence.capture_status == "captured"
    assert evidence.task_outcome == "success"
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
    assert evidence.task_outcome == "failure"
    assert evidence.errors == ("failed\n",)


def test_capture_blocks_write_command_without_explicit_approval(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    marker_path = tmp_path / "blocked.txt"

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "capture risky command",
            "--command",
            f"touch {marker_path}",
            "--command-cwd",
            str(tmp_path),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    assert not marker_path.exists()
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    execution = evidence.command_executions[0]
    assert output.harness_status == "fail"
    assert execution.exit_code == 126
    assert execution.risk_categories == ("write",)
    assert execution.approval_required
    assert not execution.approved
    assert execution.env_policy == "minimal"
    assert execution.cwd_inside_project is False


def test_capture_executes_write_command_with_explicit_approval(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    marker_path = tmp_path / "approved.txt"

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "capture approved command",
            "--command",
            f"touch {marker_path}",
            "--command-cwd",
            str(tmp_path),
            "--approve-command-risk",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    assert marker_path.exists()
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    execution = evidence.command_executions[0]
    assert output.harness_status == "pass"
    assert execution.exit_code == 0
    assert execution.risk_categories == ("write",)
    assert execution.approval_required
    assert execution.approved


def test_capture_hardens_final_artifact_contracts(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    input_path = tmp_path / "inputs" / "portfolio.json"
    output_path = tmp_path / "output" / "report.json"
    input_path.parent.mkdir(parents=True)
    output_path.parent.mkdir(parents=True)
    input_path.write_text('{"cash": 100}', encoding="utf-8")
    output_path.write_text('{"total": 100}', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "capture",
            "--goal",
            "generate finance portfolio artifacts",
            "--context",
            str(input_path),
            "--final-artifact",
            "output/report.json",
            "--command-cwd",
            str(tmp_path),
            "--outcome",
            "success",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = CaptureOutput.model_validate_json(result.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence.artifact_snapshots[0].path == "output/report.json"
    assert evidence.artifact_snapshots[0].kind == "json"
    assert evidence.artifact_contracts[0].artifact_path == "output/report.json"
    assert evidence.task_contract is not None
    assert evidence.task_contract.expected_artifacts == ("output/report.json",)
    assert evidence.record_quality is not None
    assert evidence.record_quality.strict_ready


def test_capture_workflow_uses_injected_clock_and_token_factory(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "prompt.md"
    evidence_dir = tmp_path / "evidence"
    prompt_path.write_text("Find the bug.", encoding="utf-8")

    summary = run_capture_workflow(
        CaptureRequest(
            goal="triage repo issue",
            field="local",
            runtime="codex",
            evidence_dir=evidence_dir,
            files=(CaptureFileInput(role="prompt", path=prompt_path),),
        ),
        CaptureDependencies(
            clock=lambda: datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
            token_factory=lambda: "deadbeef",
        ),
    )

    assert summary.evidence_id == "20260602T010203Z-deadbeef"
    evidence = load_evidence(summary.evidence_id, evidence_dir)
    assert evidence.created_at == datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC)
