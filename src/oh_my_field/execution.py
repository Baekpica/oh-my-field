"""Compatibility shim: moved to oh_my_field.infrastructure.process.execution."""

from oh_my_field.infrastructure.process.execution import (
    CREDENTIAL_COMMANDS,
    DANGEROUS_ENV_NAMES,
    DEFAULT_ENV_ALLOWLIST,
    DESTRUCTIVE_COMMANDS,
    EXTERNAL_COMMANDS,
    PAID_COMMANDS,
    PRODUCTION_COMMANDS,
    WRITE_COMMANDS,
    CommandEnvironment,
    CommandExecutionError,
    CommandExecutionRequest,
    CommandRiskAssessment,
    assess_command_risk,
    execute_shell_command,
)

__all__ = [
    "CREDENTIAL_COMMANDS",
    "DANGEROUS_ENV_NAMES",
    "DEFAULT_ENV_ALLOWLIST",
    "DESTRUCTIVE_COMMANDS",
    "EXTERNAL_COMMANDS",
    "PAID_COMMANDS",
    "PRODUCTION_COMMANDS",
    "WRITE_COMMANDS",
    "CommandEnvironment",
    "CommandExecutionError",
    "CommandExecutionRequest",
    "CommandRiskAssessment",
    "assess_command_risk",
    "execute_shell_command",
]
