from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

from oh_my_field.adapters.skill_install.base import resource_at
from oh_my_field.domain.skill.models import (
    ResolvedSkillInstallScope,
    SkillInstallAction,
    SkillInstallRequest,
    SkillInstallRuntime,
    SkillInstallSummary,
)
from oh_my_field.infrastructure.install import (
    read_resource_text,
    write_text_if_allowed,
)

RESOURCE_PACKAGE = "oh_my_field.resources.skills.omf"


class SkillInstallError(ValueError):
    """Raised when an OMF skill cannot be installed for the requested scope."""


@dataclass(frozen=True, slots=True)
class SkillTarget:
    resource_path: Path
    target_path: Path
    reason: str
    primary: bool = False


def install_omf_skill(request: SkillInstallRequest) -> SkillInstallSummary:
    scope = _resolve_scope(request)
    resource_root = files(RESOURCE_PACKAGE)
    actions: list[SkillInstallAction] = []
    primary_path: Path | None = None
    wrote_any = False

    for target in _skill_targets(request=request, scope=scope):
        resource = read_resource_text(resource_at(resource_root, target.resource_path))
        wrote = write_text_if_allowed(
            target_path=target.target_path,
            content=resource.content,
            overwrite=request.overwrite,
            dry_run=request.dry_run,
        )
        if target.primary:
            primary_path = target.target_path
        wrote_any = wrote_any or wrote
        actions.append(
            SkillInstallAction(
                target_path=str(target.target_path),
                action=_action_for_target(
                    target_path=target.target_path,
                    dry_run=request.dry_run,
                    wrote=wrote,
                ),
                source=resource.source,
                reason=_reason_for_target(
                    target_path=target.target_path,
                    dry_run=request.dry_run,
                    wrote=wrote,
                    target_reason=target.reason,
                ),
            ),
        )

    if primary_path is None:
        msg = "no skill target resolved for install request"
        raise SkillInstallError(msg)
    return SkillInstallSummary(
        runtime=request.runtime,
        scope=scope,
        installed=wrote_any,
        dry_run=request.dry_run,
        skill_path=str(primary_path),
        target_path=str(primary_path),
        fragment_path=None,
        profile_patch_path=None,
        patch_plan_path=None,
        actions=tuple(actions),
        next_action=_next_action(
            runtime=request.runtime,
            scope=scope,
            installed=wrote_any,
            dry_run=request.dry_run,
        ),
    )


def _resolve_scope(request: SkillInstallRequest) -> ResolvedSkillInstallScope:
    if request.scope == "auto":
        return "export" if request.runtime == "generic" else "user"
    if request.scope == "user" and request.runtime == "generic":
        msg = "generic skills can only be installed with export scope"
        raise SkillInstallError(msg)
    if request.scope == "project" and request.runtime not in ("codex", "claude_code"):
        msg = f"{request.runtime} skills do not support project scope"
        raise SkillInstallError(msg)
    if request.scope in ("user", "project", "export"):
        return request.scope
    msg = f"unsupported skill install scope {request.scope!r}"
    raise SkillInstallError(msg)


def _skill_targets(
    *,
    request: SkillInstallRequest,
    scope: ResolvedSkillInstallScope,
) -> tuple[SkillTarget, ...]:
    match scope:
        case "user":
            return _user_skill_targets(request)
        case "project":
            return _project_skill_targets(request)
        case "export":
            return _export_skill_targets(request)


def _user_skill_targets(request: SkillInstallRequest) -> tuple[SkillTarget, ...]:
    home = _home_root(request)
    match request.runtime:
        case "codex":
            skill_dir = home / ".agents" / "skills" / "omf"
            return (
                SkillTarget(
                    Path("codex/SKILL.md"),
                    skill_dir / "SKILL.md",
                    "Codex user skill written",
                    primary=True,
                ),
                SkillTarget(
                    Path("codex/agents/openai.yaml"),
                    skill_dir / "agents" / "openai.yaml",
                    "Codex skill metadata written",
                ),
            )
        case "claude_code":
            return (
                SkillTarget(
                    Path("claude_code/SKILL.md"),
                    home / ".claude" / "skills" / "omf" / "SKILL.md",
                    "Claude Code user skill written",
                    primary=True,
                ),
            )
        case "hermes":
            return (
                SkillTarget(
                    Path("hermes/SKILL.md"),
                    home / ".hermes" / "skills" / "omf" / "SKILL.md",
                    "Hermes user skill written",
                    primary=True,
                ),
            )
        case "generic":
            msg = "generic skills can only be installed with export scope"
            raise SkillInstallError(msg)


def _project_skill_targets(request: SkillInstallRequest) -> tuple[SkillTarget, ...]:
    project = request.project
    match request.runtime:
        case "codex":
            skill_dir = project / ".agents" / "skills" / "omf"
            return (
                SkillTarget(
                    Path("codex/SKILL.md"),
                    skill_dir / "SKILL.md",
                    "Codex project skill written",
                    primary=True,
                ),
                SkillTarget(
                    Path("codex/agents/openai.yaml"),
                    skill_dir / "agents" / "openai.yaml",
                    "Codex skill metadata written",
                ),
            )
        case "claude_code":
            return (
                SkillTarget(
                    Path("claude_code/SKILL.md"),
                    project / ".claude" / "skills" / "omf" / "SKILL.md",
                    "Claude Code project skill written",
                    primary=True,
                ),
            )
        case "hermes" | "generic":
            msg = f"{request.runtime} skills do not support project scope"
            raise SkillInstallError(msg)


def _export_skill_targets(request: SkillInstallRequest) -> tuple[SkillTarget, ...]:
    out_root = _resolve_output_root(request)
    match request.runtime:
        case "codex":
            skill_dir = out_root / "codex" / ".agents" / "skills" / "omf"
            return (
                SkillTarget(
                    Path("SKILL.md"),
                    out_root / "SKILL.md",
                    "shared OMF skill resource written",
                ),
                SkillTarget(
                    Path("codex/SKILL.md"),
                    skill_dir / "SKILL.md",
                    "Codex export skill written",
                    primary=True,
                ),
                SkillTarget(
                    Path("codex/agents/openai.yaml"),
                    skill_dir / "agents" / "openai.yaml",
                    "Codex skill metadata written",
                ),
            )
        case "claude_code":
            return (
                SkillTarget(
                    Path("SKILL.md"),
                    out_root / "SKILL.md",
                    "shared OMF skill resource written",
                ),
                SkillTarget(
                    Path("claude_code/SKILL.md"),
                    out_root
                    / "claude_code"
                    / ".claude"
                    / "skills"
                    / "omf"
                    / "SKILL.md",
                    "Claude Code export skill written",
                    primary=True,
                ),
            )
        case "hermes":
            return (
                SkillTarget(
                    Path("SKILL.md"),
                    out_root / "SKILL.md",
                    "shared OMF skill resource written",
                ),
                SkillTarget(
                    Path("hermes/SKILL.md"),
                    out_root / "hermes" / "skills" / "omf" / "SKILL.md",
                    "Hermes export skill written",
                    primary=True,
                ),
            )
        case "generic":
            return (
                SkillTarget(
                    Path("generic/skill.md"),
                    out_root / "generic" / "skill.md",
                    "generic export skill written",
                    primary=True,
                ),
            )


def _home_root(request: SkillInstallRequest) -> Path:
    return (request.home or Path.home()).expanduser()


def _resolve_output_root(request: SkillInstallRequest) -> Path:
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
    target_reason: str,
) -> str:
    if wrote:
        return target_reason
    if dry_run:
        return "dry-run requested"
    if target_path.exists():
        return "target exists and overwrite is false"
    return "target would be written"


def _next_action(
    *,
    runtime: SkillInstallRuntime,
    scope: ResolvedSkillInstallScope,
    installed: bool,
    dry_run: bool,
) -> str:
    if dry_run:
        return "Review the dry-run plan before installing the OMF skill."
    if not installed:
        return "Review skipped targets or rerun with --overwrite."
    action = "Open the target agent and type /omf."
    if runtime == "codex" and scope == "user":
        action = "Open Codex and type /omf; restart Codex if the skill is not listed."
    elif runtime == "codex" and scope == "project":
        action = "Open Codex from this project and type /omf."
    elif runtime == "claude_code" and scope in ("user", "project"):
        action = "Reload Claude Code if needed, then type /omf."
    elif runtime == "hermes" and scope == "user":
        action = (
            "Start Hermes and type /omf; reload skills if the session "
            "is already running."
        )
    elif scope == "export":
        action = "Review the exported OMF skill assets and copy them to the runtime."
    return action
