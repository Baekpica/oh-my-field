import json
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from oh_my_field.cli import app


def test_runtime_conformance_reports_degraded_before_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "hermes",
            "--home",
            str(home),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["runtime"] == "hermes"
    assert output["status"] == "degraded"
    checks = {check["name"]: check for check in output["checks"]}
    assert checks["controller_skill_installed"]["status"] == "fail"
    assert "omf install skill" in checks["controller_skill_installed"]["recommendation"]
    assert checks["mcp_config_present"]["status"] == "fail"
    assert checks["imported_targets_validated"]["status"] == "pass"
    assert "omf install skill" in output["next_action"]


def test_runtime_install_then_conformance_passes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    install_result = CliRunner().invoke(
        app,
        ["runtime", "install", "hermes", "--home", str(home)],
    )
    assert install_result.exit_code == 0
    install_output = _json(install_result.stdout)
    assert install_output["runtime"] == "hermes"
    assert install_output["skill"]["installed"]
    assert install_output["mcp"]["installed"]
    assert "omf runtime conformance hermes" in install_output["next_action"]

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "hermes",
            "--home",
            str(home),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "pass"
    statuses = {check["name"]: check["status"] for check in output["checks"]}
    assert statuses == {
        "controller_skill_installed": "pass",
        "mcp_config_present": "pass",
        "omf_cli_on_path": "pass",
        "capability_skills_are_launchers": "pass",
        "imported_targets_validated": "pass",
    }
    assert "conforms" in output["next_action"]


def test_runtime_conformance_flags_direct_execution_capability_skill(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    CliRunner().invoke(app, ["runtime", "install", "hermes", "--home", str(home)])
    rogue_skill = home / ".hermes" / "skills" / "front_ui" / "SKILL.md"
    rogue_skill.parent.mkdir(parents=True)
    rogue_skill.write_text(
        "# front_ui\n\n## Goal\nBuild the UI directly.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "hermes",
            "--home",
            str(home),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "degraded"
    launcher_check = next(
        check
        for check in output["checks"]
        if check["name"] == "capability_skills_are_launchers"
    )
    assert launcher_check["status"] == "fail"
    assert "front_ui" in launcher_check["detail"]
    assert "--skill-style launcher" in launcher_check["recommendation"]


def _json(stdout: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(stdout))
