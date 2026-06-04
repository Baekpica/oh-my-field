from pathlib import Path

from oh_my_field.domain.skill.models import SkillInstallRuntime


class HermesSkillInstallAdapter:
    runtime: SkillInstallRuntime = "hermes"

    def resource_paths(self) -> tuple[Path, ...]:
        return (Path("hermes/SOUL.fragment.md"),)

    def target_path(
        self,
        *,
        project: Path,
        out: Path,
        profile: str | None,
    ) -> Path:
        del project, profile
        return out / "hermes" / "SOUL.fragment.md"

    def profile_patch_path(self, *, out: Path, profile: str | None) -> Path | None:
        del profile
        return out / "hermes" / "profile.patch.yaml"

    def next_action(self, *, installed: bool, patch_plan: bool) -> str:
        del installed, patch_plan
        return "Apply the Hermes profile patch, reload the profile, then type /omf."
