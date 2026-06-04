from pathlib import Path

from oh_my_field.domain.skill.models import SkillInstallRuntime


class CodexSkillInstallAdapter:
    runtime: SkillInstallRuntime = "codex"

    def resource_paths(self) -> tuple[Path, ...]:
        return (Path("codex/AGENTS.fragment.md"),)

    def target_path(
        self,
        *,
        project: Path,
        out: Path,
        profile: str | None,
    ) -> Path:
        del out, profile
        return project / "AGENTS.md"

    def profile_patch_path(self, *, out: Path, profile: str | None) -> Path | None:
        del out, profile
        return None

    def next_action(self, *, installed: bool, patch_plan: bool) -> str:
        if installed:
            return "Open a Codex session in this project and type /omf."
        if patch_plan:
            return "Review the patch plan, merge it into AGENTS.md, then type /omf."
        return "Review the dry-run plan before installing the Codex OMF fragment."
