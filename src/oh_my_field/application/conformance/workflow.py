"""Static conformance checks for a target agent runtime.

OMF never invokes the agent runtime here; conformance verifies that the
runtime surface is wired so an agent-led run enters the OMF lifecycle
instead of bypassing it (controller skill installed, MCP config present,
capability skills installed as launchers, imported targets validated).
"""

import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.application.portability.rendering import opencode_skill_name
from oh_my_field.domain.layout import DEFAULT_CAPABILITIES_DIR
from oh_my_field.domain.models import CapabilityManifest, StrictModel
from oh_my_field.domain.skill.models import SkillInstallRequest
from oh_my_field.mcp.schemas import McpInstallRequest
from oh_my_field.storage import list_manifests, read_portability_health

type ConformanceRuntime = Literal[
    "codex", "claude_code", "hermes", "pi", "odysseus", "opencode"
]
type ConformanceCheckStatus = Literal["pass", "fail"]
type ConformanceStatus = Literal["pass", "degraded"]

OMF_MANAGED_MARKER = "omf_managed: true"


class ConformanceError(Exception):
    pass


class RuntimeConformanceRequest(StrictModel):
    runtime: ConformanceRuntime
    project: Path = Path()
    home: Path | None = None
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class RuntimeConformanceCheck(StrictModel):
    name: str = Field(min_length=1)
    status: ConformanceCheckStatus
    detail: str = Field(min_length=1)
    recommendation: str | None = None


class RuntimeConformanceSummary(StrictModel):
    runtime: ConformanceRuntime
    status: ConformanceStatus
    controller_skill_path: str
    checks: tuple[RuntimeConformanceCheck, ...]
    next_action: str = Field(min_length=1)


def run_runtime_conformance_workflow(
    request: RuntimeConformanceRequest,
) -> RuntimeConformanceSummary:
    controller_path = _controller_skill_path(request)
    manifests = tuple(list_manifests(request.capabilities_dir))
    checks = (
        _controller_skill_check(controller_path),
        _mcp_config_check(request),
        _cli_on_path_check(),
        _launcher_skills_check(
            _capability_skill_roots(request, controller_path),
            capability_skill_names=_capability_skill_names(
                request,
                manifests,
            ),
        ),
        _imported_targets_check(request, manifests),
    )
    failed = tuple(check for check in checks if check.status == "fail")
    return RuntimeConformanceSummary(
        runtime=request.runtime,
        status="degraded" if failed else "pass",
        controller_skill_path=str(controller_path),
        checks=checks,
        next_action=(
            failed[0].recommendation
            or f"review failed conformance check {failed[0].name!r}"
        )
        if failed
        else f"{request.runtime} conforms to the OMF adoption surface",
    )


def _controller_skill_path(request: RuntimeConformanceRequest) -> Path:
    summary = install_omf_skill(
        SkillInstallRequest(
            runtime=request.runtime,
            project=request.project,
            home=request.home,
            dry_run=True,
        ),
    )
    if summary.skill_path is None:
        msg = f"could not resolve controller skill path for {request.runtime!r}"
        raise ConformanceError(msg)
    return Path(summary.skill_path)


def _controller_skill_check(controller_path: Path) -> RuntimeConformanceCheck:
    if controller_path.is_file():
        return RuntimeConformanceCheck(
            name="controller_skill_installed",
            status="pass",
            detail=f"OMF controller skill found at {controller_path}",
        )
    return RuntimeConformanceCheck(
        name="controller_skill_installed",
        status="fail",
        detail=f"OMF controller skill missing at {controller_path}",
        recommendation="run `omf install skill --runtime <runtime>`",
    )


def _mcp_config_check(request: RuntimeConformanceRequest) -> RuntimeConformanceCheck:
    summary = install_mcp_config(
        McpInstallRequest(
            client=request.runtime,
            project=request.project,
            home=request.home,
            dry_run=True,
        ),
    )
    config_path = Path(summary.config_path)
    if config_path.is_file():
        return RuntimeConformanceCheck(
            name="mcp_config_present",
            status="pass",
            detail=f"MCP client config found at {config_path}",
        )
    return RuntimeConformanceCheck(
        name="mcp_config_present",
        status="fail",
        detail=f"MCP client config missing at {config_path}",
        recommendation="run `omf install mcp --client <runtime>`",
    )


def _cli_on_path_check() -> RuntimeConformanceCheck:
    omf_path = shutil.which("omf")
    if omf_path is not None:
        return RuntimeConformanceCheck(
            name="omf_cli_on_path",
            status="pass",
            detail=f"omf CLI resolved to {omf_path}",
        )
    return RuntimeConformanceCheck(
        name="omf_cli_on_path",
        status="fail",
        detail="omf CLI is not on PATH for the agent runtime",
        recommendation="install OMF (`pipx install oh-my-field`) or expose omf on PATH",
    )


def _capability_skill_roots(
    request: RuntimeConformanceRequest,
    controller_path: Path,
) -> tuple[Path, ...]:
    """Resolve every skill root the runtime discovers capability skills from.

    The controller skill root is not always where capability exports land:
    Pi installs the controller under `.pi/agent/skills` while capability
    projections install under `.pi/skills`.
    """
    roots = [controller_path.parent.parent]
    if request.runtime == "pi":
        home = (request.home or Path.home()).expanduser()
        roots.append(home / ".pi" / "skills")
        roots.append(request.project / ".pi" / "skills")
    return tuple(dict.fromkeys(root.resolve() for root in roots))


def _capability_skill_names(
    request: RuntimeConformanceRequest,
    manifests: tuple[tuple[Path, CapabilityManifest], ...],
) -> frozenset[str]:
    names = tuple(manifest.name for _, manifest in manifests)
    if request.runtime != "opencode":
        return frozenset(names)
    return frozenset(opencode_skill_name(name) for name in names)


def _launcher_skills_check(
    skill_roots: tuple[Path, ...],
    *,
    capability_skill_names: frozenset[str],
) -> RuntimeConformanceCheck:
    # Only skills matching a known OMF capability are judged; unrelated
    # native skills installed by the user are none of OMF's business.
    direct_skills = tuple(
        skill_path
        for skills_root in skill_roots
        for skill_path in sorted(skills_root.glob("*/SKILL.md"))
        if skill_path.parent.name in capability_skill_names
        and OMF_MANAGED_MARKER not in skill_path.read_text(encoding="utf-8")
    )
    scanned = ", ".join(str(root) for root in skill_roots)
    if not direct_skills:
        return RuntimeConformanceCheck(
            name="capability_skills_are_launchers",
            status="pass",
            detail=f"no direct-execution OMF capability skills under {scanned}",
        )
    names = ", ".join(path.parent.name for path in direct_skills)
    return RuntimeConformanceCheck(
        name="capability_skills_are_launchers",
        status="fail",
        detail=f"capability skills without omf_managed launcher frontmatter: {names}",
        recommendation=(
            "re-export with `omf capability export --skill-style launcher` "
            "and reinstall the launcher skill"
        ),
    )


def _imported_targets_check(
    request: RuntimeConformanceRequest,
    manifests: tuple[tuple[Path, CapabilityManifest], ...],
) -> RuntimeConformanceCheck:
    statuses = [
        (manifest.name, entry.validation_status)
        for manifest_path, manifest in manifests
        for entry in read_portability_health(manifest_path.parent).target_statuses
        if entry.target.split(":", 1)[0] == request.runtime
    ]
    if not statuses:
        return RuntimeConformanceCheck(
            name="imported_targets_validated",
            status="pass",
            detail=f"no imported {request.runtime} targets recorded",
        )
    unvalidated = tuple(name for name, status in statuses if status != "validated")
    if not unvalidated:
        return RuntimeConformanceCheck(
            name="imported_targets_validated",
            status="pass",
            detail=f"all {len(statuses)} imported {request.runtime} targets validated",
        )
    names = ", ".join(sorted(set(unvalidated)))
    return RuntimeConformanceCheck(
        name="imported_targets_validated",
        status="fail",
        detail=f"imported targets not yet validated: {names}",
        recommendation=(
            "run `omf capability validate <name> --target <runtime> "
            "--run-command <check>`"
        ),
    )
