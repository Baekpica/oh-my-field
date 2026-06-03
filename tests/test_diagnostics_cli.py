from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.diagnostics import build_doctor_summary


class VersionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    python: str
    platform: str
    schema_versions: dict[str, str]


class DoctorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    executable: str | None
    python: str
    platform: str
    cwd: str
    cwd_writable: bool
    omf_dir_creatable: bool
    git: bool
    uv: bool
    pipx: bool
    optional_runtimes: dict[str, bool]


def test_version_outputs_json_schema_versions() -> None:
    result = CliRunner().invoke(app, ["version", "--json"])

    assert result.exit_code == 0
    output = VersionOutput.model_validate_json(result.stdout)
    assert output.version == "0.1.0"
    assert output.schema_versions["capability"] == "0.1"
    assert output.schema_versions["evidence"] == "0.1"
    assert output.schema_versions["portability"] == "0.1"


def test_doctor_outputs_json_environment_summary() -> None:
    result = CliRunner().invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    output = DoctorOutput.model_validate_json(result.stdout)
    assert output.version == "0.1.0"
    assert set(output.optional_runtimes) == {"codex", "claude", "hermes-code"}


def test_doctor_checks_omf_directory_creatable_without_creating_it(
    tmp_path: Path,
) -> None:
    summary = build_doctor_summary(tmp_path)

    assert summary.omf_dir_creatable
    assert not tmp_path.joinpath(".omf").exists()
