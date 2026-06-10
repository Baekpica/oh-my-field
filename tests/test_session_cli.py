from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.infrastructure.fs.storage import load_evidence


class SessionStartOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    session_path: str
    status: str
    next_action: str


class SessionMaterializeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    evidence_id: str
    evidence_path: str
    session_path: str
    next_action: str


class SessionSuggestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    suggested_capabilities: list[str]
    session_path: str


def test_session_flow_materializes_evidence(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "sessions"
    evidence_dir = tmp_path / "evidence"

    start = CliRunner().invoke(
        app,
        [
            "session",
            "start",
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--project-root",
            str(tmp_path),
            "--goal",
            "Fix flaky tests",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    assert start.exit_code == 0
    start_output = SessionStartOutput.model_validate_json(start.stdout)

    _run_ok(
        [
            "session",
            "event",
            start_output.session_id,
            "--type",
            "command",
            "--summary",
            "ran focused tests",
            "--command",
            "uv run pytest tests/test_session_cli.py",
            "--exit-code",
            "0",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    _run_ok(
        [
            "session",
            "event",
            start_output.session_id,
            "--type",
            "user_feedback",
            "--summary",
            "looks reusable",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    _run_ok(
        [
            "session",
            "finish",
            start_output.session_id,
            "--outcome",
            "success",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )

    materialize = CliRunner().invoke(
        app,
        [
            "session",
            "materialize",
            start_output.session_id,
            "--sessions-dir",
            str(sessions_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert materialize.exit_code == 0
    output = SessionMaterializeOutput.model_validate_json(materialize.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence.session_id == start_output.session_id
    assert evidence.goal == "Fix flaky tests"
    assert evidence.runtime.name == "codex"
    assert evidence.runtime.model == "gpt-5.5"
    assert evidence.task_outcome == "success"
    assert evidence.success_or_failure_label == "success"
    assert evidence.generated_commands == ("uv run pytest tests/test_session_cli.py",)
    assert evidence.feedback == ("looks reusable",)


def test_session_suggest_capability(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "sessions"
    start = CliRunner().invoke(
        app,
        [
            "session",
            "start",
            "--runtime",
            "codex",
            "--goal",
            "Fix flaky tests!",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    assert start.exit_code == 0
    session_id = SessionStartOutput.model_validate_json(start.stdout).session_id

    suggest = CliRunner().invoke(
        app,
        [
            "session",
            "suggest-capability",
            session_id,
            "--sessions-dir",
            str(sessions_dir),
        ],
    )

    assert suggest.exit_code == 0
    output = SessionSuggestOutput.model_validate_json(suggest.stdout)
    assert output.suggested_capabilities == ["fix_flaky_tests"]


def test_session_materialize_hardens_artifact_contracts(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "sessions"
    evidence_dir = tmp_path / "evidence"
    output_path = tmp_path / "output" / "report.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text('{"total": 100}', encoding="utf-8")

    start = CliRunner().invoke(
        app,
        [
            "session",
            "start",
            "--runtime",
            "hermes",
            "--model",
            "frontier",
            "--project-root",
            str(tmp_path),
            "--goal",
            "Generate finance portfolio output",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    assert start.exit_code == 0
    session_id = SessionStartOutput.model_validate_json(start.stdout).session_id

    _run_ok(
        [
            "session",
            "event",
            session_id,
            "--type",
            "context",
            "--summary",
            "portfolio input",
            "--path",
            "inputs/portfolio.json",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    _run_ok(
        [
            "session",
            "event",
            session_id,
            "--type",
            "artifact",
            "--summary",
            "portfolio report",
            "--path",
            "output/report.json",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    _run_ok(
        [
            "session",
            "finish",
            session_id,
            "--outcome",
            "success",
            "--sessions-dir",
            str(sessions_dir),
        ],
    )

    materialize = CliRunner().invoke(
        app,
        [
            "session",
            "materialize",
            session_id,
            "--sessions-dir",
            str(sessions_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert materialize.exit_code == 0
    output = SessionMaterializeOutput.model_validate_json(materialize.stdout)
    evidence = load_evidence(output.evidence_id, evidence_dir)
    assert evidence.runtime.name == "hermes"
    assert evidence.artifact_snapshots[0].path == "output/report.json"
    assert evidence.artifact_contracts[0].artifact_path == "output/report.json"
    assert evidence.task_contract is not None
    assert evidence.task_contract.required_inputs == ("inputs/portfolio.json",)
    assert evidence.record_quality is not None
    assert evidence.record_quality.strict_ready


def _run_ok(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.stdout
