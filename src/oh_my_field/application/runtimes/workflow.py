"""Aggregate local agent-runtime state for the OMF web UI.

For each known runtime this reports three things the user cares about:
whether the runtime itself looks installed locally (a best-effort filesystem
probe), whether the OMF controller skill is installed, and whether the OMF
MCP config is present. Skill/MCP detection reuses the conformance use case
(which resolves install paths via dry-run installers and checks ``.is_file()``);
the local-presence probe is the only new signal added here.
"""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from oh_my_field.application.conformance import (
    RuntimeConformanceRequest,
    run_runtime_conformance_workflow,
)
from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR
from oh_my_field.domain.models import StrictModel
from oh_my_field.domain.skill.models import SkillInstallRequest
from oh_my_field.mcp.schemas import McpInstallRequest

type RuntimeName = Literal[
    "codex", "claude_code", "hermes", "pi", "odysseus", "opencode"
]
type RuntimePresence = Literal["present", "absent", "unknown"]
type RuntimeOverallStatus = Literal["ready", "partial", "absent"]

RUNTIME_NAMES: Final[tuple[RuntimeName, ...]] = (
    "codex",
    "claude_code",
    "hermes",
    "pi",
    "odysseus",
    "opencode",
)

# Known CLI binary per runtime (when one exists on PATH).
_RUNTIME_BINARIES: Final[dict[RuntimeName, str]] = {
    "codex": "codex",
    "claude_code": "claude",
    "hermes": "hermes-code",
}

# Home-relative config directory whose presence signals a local install.
_RUNTIME_HOME_DIRS: Final[dict[RuntimeName, Path]] = {
    "codex": Path(".codex"),
    "claude_code": Path(".claude"),
    "hermes": Path(".hermes"),
    "pi": Path(".pi"),
    "opencode": Path(".config") / "opencode",
}


class RuntimeInventoryRequest(StrictModel):
    project: Path = Path()
    home: Path | None = None
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class RuntimeState(StrictModel):
    runtime: RuntimeName
    presence: RuntimePresence
    presence_detail: str
    skill_installed: bool
    skill_path: str
    mcp_installed: bool
    mcp_config_path: str
    conformance_status: Literal["pass", "degraded"]
    overall_status: RuntimeOverallStatus
    next_action: str


class RuntimeInventorySummary(StrictModel):
    generated_at: datetime
    runtimes: tuple[RuntimeState, ...]
    ready_count: int
    present_count: int


def run_runtime_inventory_workflow(
    request: RuntimeInventoryRequest,
) -> RuntimeInventorySummary:
    home = (request.home or Path.home()).expanduser()
    runtimes = tuple(
        _runtime_state(runtime, request, home) for runtime in RUNTIME_NAMES
    )
    return RuntimeInventorySummary(
        generated_at=datetime.now(UTC),
        runtimes=runtimes,
        ready_count=sum(state.overall_status == "ready" for state in runtimes),
        present_count=sum(state.presence == "present" for state in runtimes),
    )


def _runtime_state(
    runtime: RuntimeName,
    request: RuntimeInventoryRequest,
    home: Path,
) -> RuntimeState:
    presence, presence_detail = _probe_presence(runtime, request, home)
    skill_path = _resolve_skill_path(runtime, request)
    mcp_config_path = _resolve_mcp_config_path(runtime, request)
    skill_installed = skill_path.is_file()
    mcp_installed = mcp_config_path.is_file()
    conformance = run_runtime_conformance_workflow(
        RuntimeConformanceRequest(
            runtime=runtime,
            project=request.project,
            home=request.home,
            capabilities_dir=request.capabilities_dir,
        ),
    )
    overall_status = _overall_status(
        presence=presence,
        skill_installed=skill_installed,
        mcp_installed=mcp_installed,
    )
    return RuntimeState(
        runtime=runtime,
        presence=presence,
        presence_detail=presence_detail,
        skill_installed=skill_installed,
        skill_path=str(skill_path),
        mcp_installed=mcp_installed,
        mcp_config_path=str(mcp_config_path),
        conformance_status=conformance.status,
        overall_status=overall_status,
        next_action=_next_action(
            runtime=runtime,
            presence=presence,
            conformance_status=conformance.status,
            conformance_next_action=conformance.next_action,
        ),
    )


def _probe_presence(
    runtime: RuntimeName,
    request: RuntimeInventoryRequest,
    home: Path,
) -> tuple[RuntimePresence, str]:
    binary = _RUNTIME_BINARIES.get(runtime)
    binary_path = shutil.which(binary) if binary is not None else None
    home_dir = _RUNTIME_HOME_DIRS.get(runtime)
    config_dir = home / home_dir if home_dir is not None else None
    config_found = config_dir is not None and config_dir.exists()
    if binary_path is not None:
        return "present", f"{binary} CLI on PATH at {binary_path}"
    if config_found:
        return "present", f"config directory found at {config_dir}"
    if runtime == "odysseus":
        return _probe_odysseus_presence(request)
    if binary is None:
        return "unknown", "no known CLI binary; config directory not found"
    return "absent", f"no {binary} CLI on PATH and no config directory"


def _probe_odysseus_presence(
    request: RuntimeInventoryRequest,
) -> tuple[RuntimePresence, str]:
    # Odysseus is project-scoped and ships no standalone CLI, so the only
    # local signal is its project skill tree.
    skill_root = request.project / "data" / "skills"
    if skill_root.exists():
        return "present", f"project skill tree found at {skill_root}"
    return "unknown", "project-scoped runtime; no standalone install signal"


def _resolve_skill_path(
    runtime: RuntimeName,
    request: RuntimeInventoryRequest,
) -> Path:
    summary = install_omf_skill(
        SkillInstallRequest(
            runtime=runtime,
            project=request.project,
            home=request.home,
            dry_run=True,
        ),
    )
    if summary.skill_path is None:
        return Path()
    return Path(summary.skill_path)


def _resolve_mcp_config_path(
    runtime: RuntimeName,
    request: RuntimeInventoryRequest,
) -> Path:
    summary = install_mcp_config(
        McpInstallRequest(
            client=runtime,
            project=request.project,
            home=request.home,
            dry_run=True,
        ),
    )
    return Path(summary.config_path)


def _overall_status(
    *,
    presence: RuntimePresence,
    skill_installed: bool,
    mcp_installed: bool,
) -> RuntimeOverallStatus:
    if presence == "present" and skill_installed and mcp_installed:
        return "ready"
    if presence == "absent" and not skill_installed and not mcp_installed:
        return "absent"
    return "partial"


def _next_action(
    *,
    runtime: RuntimeName,
    presence: RuntimePresence,
    conformance_status: Literal["pass", "degraded"],
    conformance_next_action: str,
) -> str:
    if conformance_status == "degraded":
        return conformance_next_action
    if presence != "present":
        return (
            f"{runtime} not detected locally; install it or run "
            f"`omf runtime install {runtime}`"
        )
    return f"{runtime} is ready for OMF"
