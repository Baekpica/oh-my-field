from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from oh_my_field.adapters.skill_install import get_skill_install_adapter, resource_at
from oh_my_field.domain.skill.models import (
    SkillInstallAction,
    SkillInstallRequest,
    SkillInstallSummary,
)
from oh_my_field.infrastructure.install import (
    read_resource_text,
    write_text_if_allowed,
)

RESOURCE_PACKAGE = "oh_my_field.resources.skills.omf"


def install_omf_skill(request: SkillInstallRequest) -> SkillInstallSummary:
    adapter = get_skill_install_adapter(request.runtime)
    resource_root = files(RESOURCE_PACKAGE)
    out_root = _resolve_output_root(request)
    actions: list[SkillInstallAction] = []
    patch_plan_path: Path | None = None

    _copy_shared_skill(
        resource_root=resource_root,
        out_root=out_root,
        request=request,
        actions=actions,
    )
    _copy_runtime_resources(
        resource_root=resource_root,
        out_root=out_root,
        request=request,
        actions=actions,
    )

    runtime_resource = read_resource_text(
        resource_at(resource_root, adapter.resource_paths()[0]),
    )
    target_path = adapter.target_path(
        project=request.project,
        out=out_root,
        profile=request.profile,
    )
    wrote_target = write_text_if_allowed(
        target_path=target_path,
        content=runtime_resource.content,
        overwrite=request.overwrite,
        dry_run=request.dry_run,
    )
    if wrote_target:
        actions.append(
            SkillInstallAction(
                target_path=str(target_path),
                action="write",
                source=runtime_resource.source,
                reason="runtime skill target written",
            ),
        )
    else:
        action = (
            "plan_only"
            if request.dry_run or not target_path.exists()
            else "skip_existing"
        )
        actions.append(
            SkillInstallAction(
                target_path=str(target_path),
                action=action,
                source=runtime_resource.source,
                reason=_skip_reason(target_path=target_path, dry_run=request.dry_run),
            ),
        )
        if target_path.exists() and not request.overwrite and not request.dry_run:
            patch_plan_path = _write_patch_plan(
                out_root=out_root,
                request=request,
                target_path=target_path,
                fragment=runtime_resource.content,
            )

    profile_patch = _copy_profile_patch(
        resource_root=resource_root,
        out_root=out_root,
        request=request,
        actions=actions,
    )
    skill_path = _skill_path(runtime=request.runtime, out_root=out_root)
    fragment_path = (
        target_path
        if wrote_target
        else _fragment_path(
            runtime=request.runtime,
            out_root=out_root,
        )
    )
    installed = wrote_target or (
        request.runtime in ("generic", "hermes") and not request.dry_run
    )
    return SkillInstallSummary(
        runtime=request.runtime,
        installed=installed,
        dry_run=request.dry_run,
        skill_path=str(skill_path) if skill_path is not None else None,
        fragment_path=str(fragment_path),
        profile_patch_path=str(profile_patch) if profile_patch is not None else None,
        patch_plan_path=str(patch_plan_path) if patch_plan_path is not None else None,
        actions=tuple(actions),
        next_action=adapter.next_action(
            installed=installed,
            patch_plan=patch_plan_path is not None,
        ),
    )


def _resolve_output_root(request: SkillInstallRequest) -> Path:
    if request.out.is_absolute():
        return request.out
    return request.project / request.out


def _copy_shared_skill(
    *,
    resource_root: Traversable,
    out_root: Path,
    request: SkillInstallRequest,
    actions: list[SkillInstallAction],
) -> None:
    resource = read_resource_text(resource_root.joinpath("SKILL.md"))
    target = out_root / "SKILL.md"
    if write_text_if_allowed(
        target_path=target,
        content=resource.content,
        overwrite=request.overwrite,
        dry_run=request.dry_run,
    ):
        actions.append(
            SkillInstallAction(
                target_path=str(target),
                action="write",
                source=resource.source,
                reason="shared OMF skill resource written",
            ),
        )


def _copy_runtime_resources(
    *,
    resource_root: Traversable,
    out_root: Path,
    request: SkillInstallRequest,
    actions: list[SkillInstallAction],
) -> None:
    adapter = get_skill_install_adapter(request.runtime)
    for relative_path in adapter.resource_paths():
        resource = read_resource_text(resource_at(resource_root, relative_path))
        target = out_root / relative_path
        if write_text_if_allowed(
            target_path=target,
            content=resource.content,
            overwrite=request.overwrite,
            dry_run=request.dry_run,
        ):
            actions.append(
                SkillInstallAction(
                    target_path=str(target),
                    action="write",
                    source=resource.source,
                    reason="runtime resource copied to install directory",
                ),
            )


def _copy_profile_patch(
    *,
    resource_root: Traversable,
    out_root: Path,
    request: SkillInstallRequest,
    actions: list[SkillInstallAction],
) -> Path | None:
    adapter = get_skill_install_adapter(request.runtime)
    profile_patch_path = adapter.profile_patch_path(
        out=out_root,
        profile=request.profile,
    )
    if profile_patch_path is None:
        return None
    resource = read_resource_text(
        resource_at(resource_root, Path("hermes/profile.patch.yaml"))
    )
    if write_text_if_allowed(
        target_path=profile_patch_path,
        content=resource.content,
        overwrite=request.overwrite,
        dry_run=request.dry_run,
    ):
        actions.append(
            SkillInstallAction(
                target_path=str(profile_patch_path),
                action="write",
                source=resource.source,
                reason="profile patch copied to install directory",
            ),
        )
    return profile_patch_path


def _write_patch_plan(
    *,
    out_root: Path,
    request: SkillInstallRequest,
    target_path: Path,
    fragment: str,
) -> Path:
    patch_plan = out_root / request.runtime / "patch-plan.md"
    patch_plan.parent.mkdir(parents=True, exist_ok=True)
    patch_plan.write_text(
        "\n".join(
            [
                "# OMF Skill Patch Plan",
                "",
                f"Target file already exists: `{target_path}`",
                "",
                "Append or merge this fragment manually:",
                "",
                "```markdown",
                fragment.rstrip(),
                "```",
                "",
            ],
        ),
        encoding="utf-8",
    )
    return patch_plan


def _skip_reason(*, target_path: Path, dry_run: bool) -> str:
    if dry_run:
        return "dry-run requested"
    if target_path.exists():
        return "target exists and overwrite is false"
    return "target would be written"


def _skill_path(*, runtime: str, out_root: Path) -> Path | None:
    if runtime == "generic":
        return out_root / "generic" / "skill.md"
    if runtime == "hermes":
        return out_root / "hermes" / "SOUL.fragment.md"
    return out_root / "SKILL.md"


def _fragment_path(*, runtime: str, out_root: Path) -> Path:
    match runtime:
        case "codex":
            return out_root / "codex" / "AGENTS.fragment.md"
        case "claude_code":
            return out_root / "claude_code" / "CLAUDE.fragment.md"
        case "hermes":
            return out_root / "hermes" / "SOUL.fragment.md"
        case _:
            return out_root / "generic" / "skill.md"
