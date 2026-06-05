import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from typer.testing import CliRunner

from oh_my_field.application.init_field import InitFieldRequest
from oh_my_field.cli import app
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR


def test_init_creates_field_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--runtime",
            "hermes",
            "--model",
            "qwen3.6-27b",
        ],
    )

    assert result.exit_code == 0
    output = _json(result.stdout)
    assert output["config_path"] == str(tmp_path / ".omf" / "config.yaml")
    for relative_path in (
        ".omf/evidence",
        "capabilities",
        ".omf/exports",
        ".omf/imports",
        ".omf/runs",
        ".omf/cache",
        ".omf/datasets",
    ):
        assert tmp_path.joinpath(relative_path).is_dir()
    assert tmp_path.joinpath(".omf", "registry.yaml").exists()
    assert tmp_path.joinpath(".omfignore").exists()

    config = yaml.safe_load(
        tmp_path.joinpath(".omf", "config.yaml").read_text(encoding="utf-8"),
    )
    assert config["schema_version"] == "omf.field_config.v0.1"
    assert config["default_runtime"] == {
        "runtime": "hermes",
        "model": "qwen3.6-27b",
    }
    assert config["storage"]["capabilities_dir"] == "capabilities"
    assert ".env*" in config["artifact_policy"]["default_excludes"]
    assert ".omf/config.yaml" in output["created_files"]


def test_init_is_idempotent_and_preserves_existing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0
    omfignore = tmp_path / ".omfignore"
    omfignore.write_text("custom/**\n", encoding="utf-8")

    second = runner.invoke(app, ["init"])

    assert second.exit_code == 0
    output = _json(second.stdout)
    assert ".omf/config.yaml" in output["existing_files"]
    assert ".omfignore" in output["existing_files"]
    assert omfignore.read_text(encoding="utf-8") == "custom/**\n"


def test_init_preserves_explicit_capabilities_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        ["init", "--capabilities-dir", ".omf/capabilities"],
    )

    assert result.exit_code == 0
    assert tmp_path.joinpath(".omf", "capabilities").is_dir()
    config = yaml.safe_load(
        tmp_path.joinpath(".omf", "config.yaml").read_text(encoding="utf-8"),
    )
    assert config["storage"]["capabilities_dir"] == ".omf/capabilities"


def test_init_request_defaults_to_canonical_capabilities_dir() -> None:
    assert InitFieldRequest().capabilities_dir == DEFAULT_CAPABILITIES_DIR


def _json(text: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(text))
