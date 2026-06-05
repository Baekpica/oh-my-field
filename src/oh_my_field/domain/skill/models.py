from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.domain.layout import DEFAULT_AGENT_SKILL_DIR
from oh_my_field.domain.models import StrictModel

type SkillInstallRuntime = Literal["codex", "claude_code", "hermes", "generic"]
type SkillInstallScope = Literal["auto", "user", "project", "export"]
type ResolvedSkillInstallScope = Literal["user", "project", "export"]


class SkillInstallRequest(StrictModel):
    runtime: SkillInstallRuntime
    project: Path = Path()
    out: Path = DEFAULT_AGENT_SKILL_DIR
    scope: SkillInstallScope = "auto"
    home: Path | None = None
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
    scope: ResolvedSkillInstallScope
    installed: bool
    dry_run: bool = False
    skill_path: str | None = None
    target_path: str | None = None
    fragment_path: str | None = None
    profile_patch_path: str | None = None
    patch_plan_path: str | None = None
    actions: tuple[SkillInstallAction, ...] = ()
    next_action: str = Field(min_length=1)
