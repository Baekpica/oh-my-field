import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from oh_my_field.infrastructure.install.mcp_config import (
    McpConfigPatchError,
    McpConfigPatchRequest,
    McpConfigPatchResult,
    McpServerConfig,
    patch_json_mcp_config,
    patch_toml_mcp_config,
    patch_yaml_mcp_config,
)
from oh_my_field.mcp.schemas import (
    McpInstallAction,
    McpInstallRequest,
    McpInstallSummary,
    ResolvedMcpInstallScope,
)

SERVER_NAME = "oh-my-field"


class McpInstallError(ValueError):
    """Raised when an MCP client config cannot be installed."""


def install_mcp_config(request: McpInstallRequest) -> McpInstallSummary:
    scope = _resolve_scope(request)
    server_command, command_needs_path_check = _server_command(request)
    server = McpServerConfig(command=server_command, args=("mcp", "serve"))
    try:
        result = _patch_config(request=request, scope=scope, server=server)
    except McpConfigPatchError as exc:
        raise McpInstallError(str(exc)) from exc
    return McpInstallSummary(
        client=request.client,
        scope=scope,
        installed=result.wrote,
        dry_run=request.dry_run,
        server_name=SERVER_NAME,
        config_path=str(result.config_path),
        backup_path=str(result.backup_path) if result.backup_path is not None else None,
        actions=(
            McpInstallAction(
                target_path=str(result.config_path),
                action=result.action,
                source=result.source,
                reason=result.reason,
            ),
        ),
        next_action=_next_action(
            request=request,
            scope=scope,
            installed=result.wrote,
            skipped=result.action == "skip_existing",
            command_needs_path_check=command_needs_path_check,
        ),
    )


def _resolve_scope(request: McpInstallRequest) -> ResolvedMcpInstallScope:
    if request.scope == "auto":
        if request.client == "generic":
            return "export"
        if request.client == "odysseus":
            return "project"
        return "user"
    if request.client == "generic" and request.scope != "export":
        msg = "generic MCP installs only support export scope"
        raise McpInstallError(msg)
    if request.client == "odysseus" and request.scope != "project":
        msg = "Odysseus MCP installs only support project scope"
        raise McpInstallError(msg)
    if request.scope == "export" and request.client != "generic":
        msg = "only the generic MCP client supports export scope"
        raise McpInstallError(msg)
    if request.scope == "project" and request.client == "hermes":
        msg = "Hermes MCP installs do not support project scope"
        raise McpInstallError(msg)
    if request.scope in ("user", "project", "export"):
        return request.scope
    msg = f"unsupported MCP install scope {request.scope!r}"
    raise McpInstallError(msg)


def _patch_config(
    *,
    request: McpInstallRequest,
    scope: ResolvedMcpInstallScope,
    server: McpServerConfig,
) -> McpConfigPatchResult:
    source = f"{request.client}:{scope}"
    config_path = _config_path(request=request, scope=scope)
    patch_request = McpConfigPatchRequest(
        config_path=config_path,
        server_name=SERVER_NAME,
        server=server,
        dry_run=request.dry_run,
        overwrite=request.overwrite,
        source=source,
    )
    match request.client:
        case "generic" | "claude_code" | "pi":
            return patch_json_mcp_config(request=patch_request)
        case "codex":
            return patch_toml_mcp_config(request=patch_request)
        case "hermes":
            return patch_yaml_mcp_config(request=patch_request)
        case "odysseus":
            return _write_odysseus_payload(request=patch_request)
    msg = f"unsupported MCP client {request.client!r}"
    raise McpInstallError(msg)


def _config_path(
    *,
    request: McpInstallRequest,
    scope: ResolvedMcpInstallScope,
) -> Path:
    if scope == "export":
        return _resolve_output_path(request)
    home = _home_root(request)
    paths = {
        ("codex", "user"): home / ".codex" / "config.toml",
        ("codex", "project"): request.project / ".codex" / "config.toml",
        ("claude_code", "user"): home / ".claude.json",
        ("claude_code", "project"): request.project / ".mcp.json",
        ("hermes", "user"): home / ".hermes" / "config.yaml",
        ("pi", "user"): home / ".pi" / "agent" / "mcp.json",
        ("pi", "project"): request.project / ".mcp.json",
        ("odysseus", "project"): (
            request.project
            / ".omf"
            / "agent"
            / "odysseus"
            / "oh-my-field.add-server.json"
        ),
    }
    path = paths.get((request.client, scope))
    if path is None:
        msg = f"{request.client} MCP installs do not support {scope} scope"
        raise McpInstallError(msg)
    return path


def _write_odysseus_payload(
    *,
    request: McpConfigPatchRequest,
) -> McpConfigPatchResult:
    if request.config_path.exists() and not request.overwrite:
        return McpConfigPatchResult(
            config_path=request.config_path,
            backup_path=None,
            action="skip_existing",
            source=request.source,
            reason="server registration payload exists and overwrite is false",
        )
    payload = {
        "method": "POST",
        "path": "/api/mcp/servers",
        "form": {
            "name": request.server_name,
            "transport": "stdio",
            "command": request.server.command,
            "args": json.dumps(list(request.server.args)),
            "env": "{}",
        },
    }
    if request.dry_run:
        return McpConfigPatchResult(
            config_path=request.config_path,
            backup_path=None,
            action="plan_only",
            source=request.source,
            reason="dry-run requested",
        )
    backup_path = _backup_existing_config(request.config_path)
    request.config_path.parent.mkdir(parents=True, exist_ok=True)
    request.config_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return McpConfigPatchResult(
        config_path=request.config_path,
        backup_path=backup_path,
        action="write",
        source=request.source,
        reason="Odysseus MCP API registration payload written",
    )


def _backup_existing_config(config_path: Path) -> Path | None:
    if not config_path.exists():
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = config_path.with_name(f"{config_path.name}.bak-{timestamp}")
    shutil.copy2(config_path, backup_path)
    return backup_path


def _resolve_output_path(request: McpInstallRequest) -> Path:
    if request.out.is_absolute():
        return request.out
    return request.project / request.out


def _home_root(request: McpInstallRequest) -> Path:
    return (request.home or Path.home()).expanduser()


def _server_command(request: McpInstallRequest) -> tuple[str, bool]:
    if request.server_command is not None:
        return request.server_command, False
    resolved = shutil.which("omf")
    if resolved is not None:
        return resolved, False
    return "omf", True


def _next_action(
    *,
    request: McpInstallRequest,
    scope: ResolvedMcpInstallScope,
    installed: bool,
    skipped: bool,
    command_needs_path_check: bool,
) -> str:
    if request.dry_run:
        return "Review the dry-run MCP config plan before installing."
    if skipped:
        return "MCP server already exists; rerun with --overwrite to replace it."
    if not installed:
        return "Review the MCP config plan or rerun with --overwrite."
    path_note = (
        " Ensure the omf executable is on PATH for the agent runtime."
        if command_needs_path_check
        else ""
    )
    action = "Verify the MCP server in the target agent client."
    if request.client == "generic" and scope == "export":
        action = "Add this MCP config to your agent client, then call omf_health."
    elif request.client == "codex":
        action = "Open Codex and run /mcp to verify oh-my-field is connected."
    elif request.client == "claude_code":
        action = "Open Claude Code and run /mcp to verify oh-my-field is connected."
    elif request.client == "hermes":
        action = "Run /reload-mcp in Hermes or restart Hermes, then use /omf."
    elif request.client == "pi":
        action = (
            "Ensure pi-mcp-adapter is installed with "
            "`pi install npm:pi-mcp-adapter`, restart Pi, then run /mcp."
        )
    elif request.client == "odysseus":
        action = (
            "Post the generated payload to Odysseus /api/mcp/servers as an "
            "admin, or add the same stdio server in Settings > MCP."
        )
    return f"{action}{path_note}"
