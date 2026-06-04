from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

from oh_my_field.domain.skill.models import SkillInstallRuntime


class SkillInstallAdapter(Protocol):
    runtime: SkillInstallRuntime

    def resource_paths(self) -> tuple[Path, ...]: ...

    def target_path(
        self,
        *,
        project: Path,
        out: Path,
        profile: str | None,
    ) -> Path: ...

    def profile_patch_path(self, *, out: Path, profile: str | None) -> Path | None:
        del out, profile
        return None

    def next_action(self, *, installed: bool, patch_plan: bool) -> str: ...


def resource_at(root: Traversable, relative_path: Path) -> Traversable:
    resource = root
    for part in relative_path.parts:
        resource = resource.joinpath(part)
    return resource
