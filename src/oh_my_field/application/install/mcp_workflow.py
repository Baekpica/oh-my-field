from importlib.resources import files
from pathlib import Path
from typing import Literal

from oh_my_field.infrastructure.install import read_resource_text, write_text_if_allowed
from oh_my_field.mcp.schemas import (
    McpInstallAction,
    McpInstallRequest,
    McpInstallSummary,
)

RESOURCE_PACKAGE = "oh_my_field.resources.mcp"


def install_mcp_config(request: McpInstallRequest) -> McpInstallSummary:
    resource = read_resource_text(files(RESOURCE_PACKAGE).joinpath("generic.json"))
    target_path = _resolve_output_path(request)
    wrote = write_text_if_allowed(
        target_path=target_path,
        content=resource.content,
        overwrite=request.overwrite,
        dry_run=request.dry_run,
    )
    action = _action_for_target(
        target_path=target_path,
        dry_run=request.dry_run,
        wrote=wrote,
    )
    return McpInstallSummary(
        client=request.client,
        installed=wrote,
        dry_run=request.dry_run,
        config_path=str(target_path),
        actions=(
            McpInstallAction(
                target_path=str(target_path),
                action=action,
                source=resource.source,
                reason=_reason_for_target(
                    target_path=target_path,
                    dry_run=request.dry_run,
                    wrote=wrote,
                ),
            ),
        ),
        next_action=_next_action(installed=wrote),
    )


def _resolve_output_path(request: McpInstallRequest) -> Path:
    if request.out.is_absolute():
        return request.out
    return request.project / request.out


def _action_for_target(
    *,
    target_path: Path,
    dry_run: bool,
    wrote: bool,
) -> Literal["write", "skip_existing", "plan_only"]:
    if wrote:
        return "write"
    if dry_run or not target_path.exists():
        return "plan_only"
    return "skip_existing"


def _reason_for_target(
    *,
    target_path: Path,
    dry_run: bool,
    wrote: bool,
) -> str:
    if wrote:
        return "generic MCP server config written"
    if dry_run:
        return "dry-run requested"
    if target_path.exists():
        return "target exists and overwrite is false"
    return "target would be written"


def _next_action(*, installed: bool) -> str:
    if installed:
        return "Add this MCP config to your agent client, then call omf_health."
    return "Review the planned MCP config or rerun with --overwrite."
