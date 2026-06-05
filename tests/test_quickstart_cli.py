import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from oh_my_field.cli import app


def test_quickstart_import_promote_health_flow(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.log"
    test_result_path = tmp_path / "pytest.txt"
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    log_path.write_text("agent run log\n", encoding="utf-8")
    test_result_path.write_text("pytest passed\n", encoding="utf-8")

    runner = CliRunner()
    import_result = runner.invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "triage repo issue",
            "--test-result",
            str(test_result_path),
            "--evidence-dir",
            str(evidence_dir),
            "--outcome",
            "success",
        ],
    )

    assert import_result.exit_code == 0
    evidence_id = str(_json(import_result.stdout)["evidence_id"])

    promote_result = runner.invoke(
        app,
        [
            "promote",
            evidence_id,
            "--name",
            "repo_issue_triage",
            "--description",
            "Repository issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert promote_result.exit_code == 0

    health_result = runner.invoke(
        app,
        [
            "health",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert health_result.exit_code == 0
    health = _json(health_result.stdout)
    assert health["capability_name"] == "repo_issue_triage"
    entries = cast("list[dict[str, Any]]", health["entries"])
    assert entries[0]["evidence_count"] == 1


def test_init_then_default_promote_health_use_same_capabilities_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "codex.log"
    test_result_path = tmp_path / "pytest.txt"
    log_path.write_text("agent run log\n", encoding="utf-8")
    test_result_path.write_text("pytest passed\n", encoding="utf-8")

    runner = CliRunner()
    init_result = runner.invoke(app, ["init"])

    assert init_result.exit_code == 0

    import_result = runner.invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "triage repo issue",
            "--test-result",
            str(test_result_path),
            "--outcome",
            "success",
        ],
    )

    assert import_result.exit_code == 0
    evidence_id = str(_json(import_result.stdout)["evidence_id"])

    promote_result = runner.invoke(
        app,
        [
            "promote",
            evidence_id,
            "--name",
            "repo_issue_triage",
            "--description",
            "Repository issue triage capability",
        ],
    )

    assert promote_result.exit_code == 0

    health_result = runner.invoke(app, ["health", "repo_issue_triage"])

    assert health_result.exit_code == 0
    assert tmp_path.joinpath(
        "capabilities",
        "repo_issue_triage",
        "capability.yaml",
    ).exists()
    assert not tmp_path.joinpath(".omf", "capabilities", "repo_issue_triage").exists()


def _json(text: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(text))
