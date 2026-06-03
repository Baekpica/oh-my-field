from pathlib import Path

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
    assert evidence.runtime.tools == ("external_agent_log",)
    assert [file.role for file in evidence.files] == [
        "artifact",
        "diff",
        "test_result",
    ]
    assert evidence.tool_calls[0].tool == "runtime_adapter.capture_run"
    assert evidence.integrity_chain[-1].artifact_type == "evidence"
