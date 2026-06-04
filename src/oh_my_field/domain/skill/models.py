from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.domain.models import StrictModel

type SkillInstallRuntime = Literal["codex", "claude_code", "hermes", "generic"]


class SkillInstallRequest(StrictModel):
    runtime: SkillInstallRuntime
    project: Path = Path()
    out: Path = Path(".omf/agent/omf-skill")
    profile: str | None = None
    dry_run: bool = False
    overwrite: bool = False


class SkillInstallAction(StrictModel):
    target_path: str
    action: Literal["write", "skip_existing", "plan_only"]
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class SkillInstallSummary(StrictModel):
    runtime: SkillInstallRuntime
    installed: bool
    dry_run: bool = False
    skill_path: str | None = None
    fragment_path: str | None = None
    profile_patch_path: str | None = None
    patch_plan_path: str | None = None
    actions: tuple[SkillInstallAction, ...] = ()
    next_action: str = Field(min_length=1)
