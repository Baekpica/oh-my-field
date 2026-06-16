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


def test_opencode_runtime_install_then_conformance_passes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    install_result = CliRunner().invoke(
        app,
        ["runtime", "install", "opencode", "--home", str(home)],
    )
    assert install_result.exit_code == 0
    install_output = _json(install_result.stdout)
    assert install_output["runtime"] == "opencode"
    assert install_output["skill"]["skill_path"] == str(
        home / ".config" / "opencode" / "skills" / "omf" / "SKILL.md",
    )
    assert install_output["mcp"]["config_path"] == str(
        home / ".config" / "opencode" / "opencode.json",
    )
    assert "omf runtime conformance opencode" in install_output["next_action"]

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "opencode",
            "--home",
            str(home),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["runtime"] == "opencode"
    assert output["status"] == "pass"


def test_runtime_conformance_flags_direct_execution_capability_skill(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    capabilities_dir = tmp_path / "capabilities"
    _create_capability(tmp_path, "front_ui", capabilities_dir)
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
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "degraded"
    launcher_check = _launcher_check(output)
    assert launcher_check["status"] == "fail"
    assert "front_ui" in launcher_check["detail"]
    assert "--skill-style launcher" in launcher_check["recommendation"]


def test_runtime_conformance_ignores_unrelated_native_skills(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    capabilities_dir = tmp_path / "capabilities"
    _create_capability(tmp_path, "front_ui", capabilities_dir)
    CliRunner().invoke(app, ["runtime", "install", "hermes", "--home", str(home)])
    # A native skill the user installed themselves, unrelated to any OMF
    # capability, must not degrade conformance.
    native_skill = home / ".hermes" / "skills" / "weather_helper" / "SKILL.md"
    native_skill.parent.mkdir(parents=True)
    native_skill.write_text(
        "# weather_helper\n\nFetch the weather and answer directly.\n",
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
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "pass"
    assert _launcher_check(output)["status"] == "pass"


def test_runtime_conformance_flags_opencode_hyphenated_direct_skill(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    capabilities_dir = tmp_path / "capabilities"
    _create_capability(tmp_path, "repo_issue_triage", capabilities_dir)
    CliRunner().invoke(app, ["runtime", "install", "opencode", "--home", str(home)])
    rogue_skill = (
        home / ".config" / "opencode" / "skills" / "repo-issue-triage" / "SKILL.md"
    )
    rogue_skill.parent.mkdir(parents=True)
    rogue_skill.write_text(
        "# repo_issue_triage\n\n## Goal\nRun the capability directly.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "opencode",
            "--home",
            str(home),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "degraded"
    launcher_check = _launcher_check(output)
    assert launcher_check["status"] == "fail"
    assert "repo-issue-triage" in launcher_check["detail"]


def test_runtime_conformance_flags_opencode_project_direct_skill(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    capabilities_dir = tmp_path / "capabilities"
    _create_capability(tmp_path, "repo_issue_triage", capabilities_dir)
    CliRunner().invoke(app, ["runtime", "install", "opencode", "--home", str(home)])
    rogue_skill = project / ".opencode" / "skills" / "repo-issue-triage" / "SKILL.md"
    rogue_skill.parent.mkdir(parents=True)
    rogue_skill.write_text(
        "# repo_issue_triage\n\n## Goal\nRun the project capability directly.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "runtime",
            "conformance",
            "opencode",
            "--home",
            str(home),
            "--project",
            str(project),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "degraded"
    launcher_check = _launcher_check(output)
    assert launcher_check["status"] == "fail"
    assert "repo-issue-triage" in launcher_check["detail"]


def test_runtime_conformance_flags_direct_execution_skill_in_pi_skill_root(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    capabilities_dir = tmp_path / "capabilities"
    _create_capability(tmp_path, "front_ui", capabilities_dir)
    install_result = CliRunner().invoke(
        app,
        ["runtime", "install", "pi", "--home", str(home)],
    )
    assert install_result.exit_code == 0
    # Pi capability exports install under .pi/skills, not the controller's
    # .pi/agent/skills root.
    rogue_skill = home / ".pi" / "skills" / "front_ui" / "SKILL.md"
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
            "pi",
            "--home",
            str(home),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["status"] == "degraded"
    launcher_check = _launcher_check(output)
    assert launcher_check["status"] == "fail"
    assert "front_ui" in launcher_check["detail"]


def _create_capability(
    tmp_path: Path,
    name: str,
    capabilities_dir: Path,
) -> None:
    log_path = tmp_path / f"{name}.log"
    evidence_dir = tmp_path / "evidence"
    log_path.write_text("Agent completed the task.\n", encoding="utf-8")
    import_result = CliRunner().invoke(
        app,
        [
            "import-run",
            "codex",
            "--log",
            str(log_path),
            "--goal",
            "build the front ui",
            "--outcome",
            "success",
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    assert import_result.exit_code == 0, import_result.output
    evidence_id = cast(
        "str",
        json.loads(import_result.stdout)["evidence_id"],
    )
    promote_result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence_id,
            "--name",
            name,
            "--description",
            "Front UI capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )
    assert promote_result.exit_code == 0, promote_result.output


def _launcher_check(output: dict[str, Any]) -> dict[str, Any]:
    return next(
        check
        for check in output["checks"]
        if check["name"] == "capability_skills_are_launchers"
    )


def _json(stdout: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(stdout))
