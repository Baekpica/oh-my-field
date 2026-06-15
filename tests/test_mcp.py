import json
import tomllib
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field import __version__
from oh_my_field.cli import app
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR
from oh_my_field.mcp.schemas import (
    ExportCapabilityToolRequest,
    HealthToolRequest,
    PromoteCapabilityToolRequest,
)
from oh_my_field.mcp.server import handle_message
from oh_my_field.mcp.tools import dispatch_tool, mcp_tool_definitions


class InstallMcpOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client: str
    scope: str
    installed: bool
    dry_run: bool
    server_name: str
    config_path: str
    backup_path: str | None
    actions: list[dict[str, object]]
    next_action: str


def test_mcp_tools_cover_session_promote_export_and_health(tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".omf" / "sessions"
    evidence_dir = tmp_path / ".omf" / "evidence"
    eval_dir = tmp_path / ".omf" / "evals"
    capabilities_dir = tmp_path / "capabilities"

    artifact_path = tmp_path / "output" / "report.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text('{"ok": true}', encoding="utf-8")

    start = dispatch_tool(
        "omf_start_session",
        {
            "runtime": "codex",
            "model": "gpt-5.5",
            "project_root": str(tmp_path),
            "goal": "refactor portability",
            "sessions_dir": str(sessions_dir),
        },
    )
    session_id = cast("str", start["session_id"])

    event = dispatch_tool(
        "omf_record_event",
        {
            "session_id": session_id,
            "type": "command",
            "summary": "ran focused tests",
            "command": "uv run pytest tests/test_portability_cli.py",
            "exit_code": 0,
            "risk_categories": ["write"],
            "sessions_dir": str(sessions_dir),
        },
    )
    assert event["event_count"] == 2
    assert "next_action" in event

    dispatch_tool(
        "omf_record_input",
        {
            "session_id": session_id,
            "path": "AGENTS.md",
            "summary": "required project instructions",
            "sessions_dir": str(sessions_dir),
        },
    )
    dispatch_tool(
        "omf_record_artifact",
        {
            "session_id": session_id,
            "path": "output/report.json",
            "summary": "final generated report",
            "sessions_dir": str(sessions_dir),
        },
    )
    dispatch_tool(
        "omf_record_validation",
        {
            "session_id": session_id,
            "summary": "artifact contract validation passed",
            "command": "python validators/validate_contract.py",
            "exit_code": 0,
            "artifact_path": "output/report.json",
            "sessions_dir": str(sessions_dir),
        },
    )
    decision = dispatch_tool(
        "omf_record_decision",
        {
            "session_id": session_id,
            "summary": "promote as a reusable portability capability",
            "sessions_dir": str(sessions_dir),
        },
    )
    assert decision["event_count"] == 6

    finish = dispatch_tool(
        "omf_finish_session",
        {
            "session_id": session_id,
            "outcome": "success",
            "sessions_dir": str(sessions_dir),
        },
    )
    assert finish["status"] == "completed"

    materialized = dispatch_tool(
        "omf_materialize_session",
        {
            "session_id": session_id,
            "sessions_dir": str(sessions_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    evidence_id = cast("str", materialized["evidence_id"])
    assert Path(cast("str", materialized["evidence_path"])).exists()

    promoted = dispatch_tool(
        "omf_promote_capability",
        {
            "evidence_id": evidence_id,
            "name": "refactor_portability",
            "description": "Refactor portability code safely.",
            "evidence_dir": str(evidence_dir),
            "eval_dir": str(eval_dir),
            "capabilities_dir": str(capabilities_dir),
        },
    )
    assert Path(cast("str", promoted["manifest_path"])).exists()

    health = dispatch_tool(
        "omf_health",
        {
            "capability_name": "refactor_portability",
            "capabilities_dir": str(capabilities_dir),
            "eval_dir": str(eval_dir),
        },
    )
    assert health["count"] == 1

    exported = dispatch_tool(
        "omf_export_capability",
        {
            "capability_name": "refactor_portability",
            "target": "generic",
            "out": str(tmp_path / ".omf" / "exports" / "refactor"),
            "capabilities_dir": str(capabilities_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    assert Path(cast("str", exported["export_path"])).exists()


def test_mcp_tools_list_uses_json_schema() -> None:
    tools = mcp_tool_definitions()
    names = {cast("str", tool["name"]) for tool in tools}
    assert "omf_start_session" in names
    assert "omf_record_input" in names
    assert "omf_record_artifact" in names
    assert "omf_record_validation" in names
    assert "omf_record_decision" in names
    assert "omf_health" in names
    start = next(tool for tool in tools if tool["name"] == "omf_start_session")
    schema = cast("dict[str, object]", start["inputSchema"])
    assert schema["type"] == "object"


def test_mcp_validate_does_not_expose_command_risk_self_approval() -> None:
    # MCP arguments are prompt-controlled, so the validate surface must not let a
    # client self-approve risky commands or restore stripped secret env vars.
    tools = {cast("str", tool["name"]): tool for tool in mcp_tool_definitions()}
    schema = cast("dict[str, object]", tools["omf_validate_capability"]["inputSchema"])
    properties = cast("dict[str, object]", schema["properties"])
    assert "approve_command_risk" not in properties
    assert "allow_env" not in properties


def test_mcp_default_layout_matches_canonical_capabilities_dir() -> None:
    assert (
        PromoteCapabilityToolRequest.model_fields["capabilities_dir"].default
        == DEFAULT_CAPABILITIES_DIR
    )
    assert (
        ExportCapabilityToolRequest.model_fields["capabilities_dir"].default
        == DEFAULT_CAPABILITIES_DIR
    )
    assert (
        HealthToolRequest.model_fields["capabilities_dir"].default
        == DEFAULT_CAPABILITIES_DIR
    )


def test_mcp_server_handles_tools_list_jsonrpc() -> None:
    response = handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response is not None
    assert response["jsonrpc"] == "2.0"
    result = cast("dict[str, object]", response["result"])
    tools = cast("list[dict[str, object]]", result["tools"])
    assert any(tool["name"] == "omf_health" for tool in tools)


def test_mcp_server_initialize_uses_package_version() -> None:
    response = handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )

    assert response is not None
    result = cast("dict[str, object]", response["result"])
    server_info = cast("dict[str, object]", result["serverInfo"])
    assert server_info == {"name": "oh-my-field", "version": __version__}


def test_install_mcp_generic_writes_config(tmp_path: Path) -> None:
    out = tmp_path / ".omf" / "mcp.json"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "generic",
            "--project",
            str(tmp_path),
            "--out",
            str(out),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    assert output.client == "generic"
    assert output.scope == "export"
    assert output.installed
    assert output.config_path == str(out)
    assert output.backup_path is None
    config = json.loads(out.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "omf"
    assert config["mcpServers"]["oh-my-field"]["args"] == ["mcp", "serve"]


def test_install_mcp_codex_patches_user_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_command = tmp_path / "fake-omf"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "codex",
            "--home",
            str(home),
            "--server-command",
            str(fake_command),
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    config_path = home / ".codex" / "config.toml"
    assert output.client == "codex"
    assert output.scope == "user"
    assert output.installed
    assert output.config_path == str(config_path)
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    server = config["mcp_servers"]["oh-my-field"]
    assert server["command"] == str(fake_command)
    assert server["args"] == ["mcp", "serve"]


def test_install_mcp_claude_project_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "claude_code",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    config_path = tmp_path / ".mcp.json"
    assert output.scope == "project"
    assert output.config_path == str(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "omf"


def test_install_mcp_hermes_patches_yaml(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "hermes",
            "--home",
            str(home),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    config_path = home / ".hermes" / "config.yaml"
    assert output.config_path == str(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["mcp_servers"]["oh-my-field"]["command"] == "omf"
    assert config["mcp_servers"]["oh-my-field"]["args"] == ["mcp", "serve"]


def test_install_mcp_pi_project_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "pi",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    config_path = tmp_path / ".mcp.json"
    assert output.client == "pi"
    assert output.scope == "project"
    assert output.config_path == str(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "omf"
    assert config["mcpServers"]["oh-my-field"]["args"] == ["mcp", "serve"]


def test_install_mcp_odysseus_project_config(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "odysseus",
            "--scope",
            "project",
            "--project",
            str(tmp_path),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    config_path = (
        tmp_path / ".omf" / "agent" / "odysseus" / "oh-my-field.add-server.json"
    )
    assert output.client == "odysseus"
    assert output.scope == "project"
    assert output.config_path == str(config_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/mcp/servers"
    assert payload["form"]["name"] == "oh-my-field"
    assert payload["form"]["transport"] == "stdio"
    assert payload["form"]["command"] == "omf"
    assert payload["form"]["args"] == '["mcp", "serve"]'


def test_install_mcp_existing_server_skips_without_overwrite(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config_path = home / ".claude.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "oh-my-field": {"command": "existing", "args": []},
                },
            },
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "claude_code",
            "--home",
            str(home),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    assert not output.installed
    assert output.backup_path is None
    assert output.actions[0]["action"] == "skip_existing"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "existing"


def test_install_mcp_overwrite_creates_backup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config_path = home / ".claude.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "oh-my-field": {"command": "existing", "args": []},
                },
            },
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "claude_code",
            "--home",
            str(home),
            "--server-command",
            "omf",
            "--overwrite",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    assert output.installed
    assert output.backup_path is not None
    assert Path(output.backup_path).exists()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "omf"


def test_install_mcp_rejects_invalid_existing_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config_path = home / ".claude.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{not-json", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "claude_code",
            "--home",
            str(home),
            "--server-command",
            "omf",
        ],
    )

    assert result.exit_code == 1
    assert "invalid JSON MCP config" in result.stderr
    assert config_path.read_text(encoding="utf-8") == "{not-json"


def test_install_mcp_dry_run_writes_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = CliRunner().invoke(
        app,
        [
            "install",
            "mcp",
            "--client",
            "codex",
            "--home",
            str(home),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    assert output.dry_run
    assert not output.installed
    assert output.actions[0]["action"] == "plan_only"
    assert not home.exists()


def test_mcp_adoption_tools_list_inspect_and_validate(tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".omf" / "sessions"
    evidence_dir = tmp_path / ".omf" / "evidence"
    eval_dir = tmp_path / ".omf" / "evals"
    capabilities_dir = tmp_path / "capabilities"
    target_capabilities_dir = tmp_path / "target-capabilities"
    export_dir = tmp_path / ".omf" / "exports" / "adoption"
    artifact_path = tmp_path / "output" / "report.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text('{"ok": true}', encoding="utf-8")

    start = dispatch_tool(
        "omf_start_session",
        {
            "runtime": "codex",
            "model": "gpt-5.5",
            "project_root": str(tmp_path),
            "goal": "adopt portability",
            "sessions_dir": str(sessions_dir),
        },
    )
    session_id = cast("str", start["session_id"])
    dispatch_tool(
        "omf_record_input",
        {
            "session_id": session_id,
            "path": "AGENTS.md",
            "summary": "required project instructions",
            "sessions_dir": str(sessions_dir),
        },
    )
    dispatch_tool(
        "omf_record_artifact",
        {
            "session_id": session_id,
            "path": "output/report.json",
            "summary": "final generated report",
            "sessions_dir": str(sessions_dir),
        },
    )
    dispatch_tool(
        "omf_record_validation",
        {
            "session_id": session_id,
            "summary": "artifact contract validation passed",
            "command": "python validators/validate_contract.py",
            "exit_code": 0,
            "artifact_path": "output/report.json",
            "sessions_dir": str(sessions_dir),
        },
    )
    dispatch_tool(
        "omf_finish_session",
        {
            "session_id": session_id,
            "outcome": "success",
            "sessions_dir": str(sessions_dir),
        },
    )
    materialized = dispatch_tool(
        "omf_materialize_session",
        {
            "session_id": session_id,
            "sessions_dir": str(sessions_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    dispatch_tool(
        "omf_promote_capability",
        {
            "evidence_id": cast("str", materialized["evidence_id"]),
            "name": "adopt_portability",
            "description": "Adopt portability capability safely.",
            "evidence_dir": str(evidence_dir),
            "eval_dir": str(eval_dir),
            "capabilities_dir": str(capabilities_dir),
        },
    )

    listed = dispatch_tool(
        "omf_list_capabilities",
        {
            "capabilities_dir": str(capabilities_dir),
            "eval_dir": str(eval_dir),
        },
    )
    assert listed["count"] == 1
    registry = cast("dict[str, object]", listed["registry"])
    entries = cast("list[dict[str, object]]", registry["entries"])
    assert entries[0]["name"] == "adopt_portability"

    inspected = dispatch_tool(
        "omf_inspect_capability",
        {
            "capability_name": "adopt_portability",
            "capabilities_dir": str(capabilities_dir),
        },
    )
    assert inspected["capability_name"] == "adopt_portability"
    assert inspected["normalized_goal"] == "adopt portability"
    assert inspected["runtime_name"] == "codex"
    assert inspected["required_checks"]

    exported = dispatch_tool(
        "omf_export_capability",
        {
            "capability_name": "adopt_portability",
            "target": "codex",
            "target_model": "gpt-5.5",
            "out": str(export_dir),
            "capabilities_dir": str(capabilities_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    import_result = CliRunner().invoke(
        app,
        [
            "capability",
            "import",
            cast("str", exported["export_path"]),
            "--runtime",
            "codex",
            "--model",
            "gpt-5.5",
            "--capabilities-dir",
            str(target_capabilities_dir),
            "--eval-dir",
            str(eval_dir),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )
    assert import_result.exit_code == 0

    validated = dispatch_tool(
        "omf_validate_capability",
        {
            "capability_name": "adopt_portability",
            "target": "codex",
            "model": "gpt-5.5",
            "capabilities_dir": str(target_capabilities_dir),
            "eval_dir": str(eval_dir),
            "evidence_dir": str(evidence_dir),
        },
    )
    assert validated["capability_name"] == "adopt_portability"
    assert validated["status"] in {"needs_validation", "needs_adaptation", "validated"}
    assert validated["manual_run_required"] is True
