from pathlib import Path

from oh_my_field.domain.skill.models import SkillInstallRuntime


class GenericSkillInstallAdapter:
    runtime: SkillInstallRuntime = "generic"

    def resource_paths(self) -> tuple[Path, ...]:
        return (Path("generic/skill.md"),)

    def target_path(
        self,
        *,
        project: Path,
        out: Path,
        profile: str | None,
    ) -> Path:
        del project, profile
        return out / "generic" / "skill.md"

    def profile_patch_path(self, *, out: Path, profile: str | None) -> Path | None:
        del out, profile
        return None

    def next_action(self, *, installed: bool, patch_plan: bool) -> str:
        del patch_plan
        if installed:
            return "Point the target agent at the generated generic OMF skill file."
        return "Review the dry-run plan before writing the generic OMF skill."
