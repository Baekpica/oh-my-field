import json
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

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
    installed: bool
    dry_run: bool
    server_name: str
    config_path: str
    actions: list[dict[str, object]]
    next_action: str


def test_mcp_tools_cover_session_promote_export_and_health(tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".omf" / "sessions"
    evidence_dir = tmp_path / ".omf" / "evidence"
    eval_dir = tmp_path / ".omf" / "evals"
    capabilities_dir = tmp_path / "capabilities"

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
    assert "omf_health" in names
    start = next(tool for tool in tools if tool["name"] == "omf_start_session")
    schema = cast("dict[str, object]", start["inputSchema"])
    assert schema["type"] == "object"


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
        ],
    )

    assert result.exit_code == 0
    output = InstallMcpOutput.model_validate_json(result.stdout)
    assert output.installed
    assert output.config_path == str(out)
    config = json.loads(out.read_text(encoding="utf-8"))
    assert config["mcpServers"]["oh-my-field"]["command"] == "omf"
    assert config["mcpServers"]["oh-my-field"]["args"] == ["mcp", "serve"]
