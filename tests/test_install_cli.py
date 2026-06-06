from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app


class InstallSkillOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: str
    scope: str
    installed: bool
    dry_run: bool
    skill_path: str | None
    target_path: str | None
    fragment_path: str | None
    profile_patch_path: str | None
    patch_plan_path: str | None
    actions: list[dict[str, object]]
    next_action: str


def test_install_skill_generic_writes_out_resource(tmp_path: Path) -> None:
    out_dir = tmp_path / "omf-skill"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "generic",
            "--project",
            str(tmp_path),
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = out_dir / "generic" / "skill.md"
    assert output.runtime == "generic"
    assert output.scope == "export"
    assert output.installed
    assert output.skill_path == str(skill_path)
    assert output.target_path == str(skill_path)
    assert output.patch_plan_path is None
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: omf" in content
    assert "OMF Meta-Skill" in content


def test_install_skill_codex_defaults_to_user_skill_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "codex",
            "--home",
            str(home),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = home / ".agents" / "skills" / "omf" / "SKILL.md"
    metadata_path = skill_path.parent / "agents" / "openai.yaml"
    assert output.runtime == "codex"
    assert output.scope == "user"
    assert output.installed
    assert output.skill_path == str(skill_path)
    assert skill_path.exists()
    assert metadata_path.exists()
    assert "name: omf" in skill_path.read_text(encoding="utf-8")


def test_install_skill_pi_defaults_to_user_skill_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "pi",
            "--home",
            str(home),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = home / ".pi" / "agent" / "skills" / "omf" / "SKILL.md"
    assert output.runtime == "pi"
    assert output.scope == "user"
    assert output.installed
    assert output.skill_path == str(skill_path)
    assert skill_path.exists()
    assert "name: omf" in skill_path.read_text(encoding="utf-8")


def test_install_skill_project_scope_writes_project_discovery_path(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "claude_code",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = tmp_path / ".claude" / "skills" / "omf" / "SKILL.md"
    assert output.scope == "project"
    assert output.installed
    assert output.skill_path == str(skill_path)
    assert "name: omf" in skill_path.read_text(encoding="utf-8")


def test_install_skill_odysseus_project_scope_writes_data_skill(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "odysseus",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = tmp_path / "data" / "skills" / "omf" / "omf" / "SKILL.md"
    assert output.runtime == "odysseus"
    assert output.scope == "project"
    assert output.installed
    assert output.skill_path == str(skill_path)
    content = skill_path.read_text(encoding="utf-8")
    assert "name: omf" in content
    assert "category: omf" in content


def test_install_skill_export_scope_writes_reviewable_layout(tmp_path: Path) -> None:
    out_dir = tmp_path / "omf-skill"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "hermes",
            "--scope",
            "export",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    skill_path = out_dir / "hermes" / "skills" / "omf" / "SKILL.md"
    assert output.scope == "export"
    assert output.skill_path == str(skill_path)
    assert skill_path.exists()
    assert out_dir.joinpath("SKILL.md").exists()


def test_install_skill_duplicate_skips_without_overwrite(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skill_path = home / ".hermes" / "skills" / "omf" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Existing\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "hermes",
            "--home",
            str(home),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    assert not output.installed
    assert output.actions[0]["action"] == "skip_existing"
    assert skill_path.read_text(encoding="utf-8") == "# Existing\n"


def test_install_skill_dry_run_writes_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "hermes",
            "--home",
            str(home),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    assert output.runtime == "hermes"
    assert output.scope == "user"
    assert output.dry_run
    assert not output.installed
    assert not home.exists()


def test_install_skill_rejects_unsupported_project_scope(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "hermes",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "do not support project scope" in result.stderr
