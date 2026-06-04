from oh_my_field.adapters.skill_install.base import (
    SkillInstallAdapter,
    resource_at,
)
from oh_my_field.adapters.skill_install.claude_code import (
    ClaudeCodeSkillInstallAdapter,
)
from oh_my_field.adapters.skill_install.codex import CodexSkillInstallAdapter
from oh_my_field.adapters.skill_install.generic import GenericSkillInstallAdapter
from oh_my_field.adapters.skill_install.hermes import HermesSkillInstallAdapter
from oh_my_field.domain.skill.models import SkillInstallRuntime

_ADAPTERS: dict[SkillInstallRuntime, SkillInstallAdapter] = {
    "claude_code": ClaudeCodeSkillInstallAdapter(),
    "codex": CodexSkillInstallAdapter(),
    "generic": GenericSkillInstallAdapter(),
    "hermes": HermesSkillInstallAdapter(),
}


def get_skill_install_adapter(runtime: SkillInstallRuntime) -> SkillInstallAdapter:
    return _ADAPTERS[runtime]


__all__ = [
    "SkillInstallAdapter",
    "get_skill_install_adapter",
    "resource_at",
]
