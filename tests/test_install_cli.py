from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app


class InstallSkillOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: str
    installed: bool
    dry_run: bool
    skill_path: str | None
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
    assert output.installed
    assert output.skill_path == str(skill_path)
    assert skill_path.exists()
    assert "OMF Meta-Skill" in skill_path.read_text(encoding="utf-8")


def test_install_skill_codex_preserves_existing_agents(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text("# Existing\n", encoding="utf-8")
    out_dir = tmp_path / ".omf" / "agent" / "omf-skill"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "codex",
            "--project",
            str(tmp_path),
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    assert not output.installed
    assert output.patch_plan_path is not None
    assert agents_path.read_text(encoding="utf-8") == "# Existing\n"
    assert Path(output.patch_plan_path).exists()
    assert "OMF Tracking" in Path(output.patch_plan_path).read_text(
        encoding="utf-8",
    )


def test_install_skill_dry_run_writes_nothing(tmp_path: Path) -> None:
    out_dir = tmp_path / "omf-skill"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "skill",
            "--runtime",
            "hermes",
            "--project",
            str(tmp_path),
            "--profile",
            "hermes-code",
            "--out",
            str(out_dir),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    output = InstallSkillOutput.model_validate_json(result.stdout)
    assert output.runtime == "hermes"
    assert output.dry_run
    assert not output.installed
    assert not out_dir.exists()
