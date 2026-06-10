import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from oh_my_field.models import (
    COMMAND_RISK_CATEGORIES,
    CommandExecution,
    CommandRiskCategory,
)

WRITE_COMMANDS: Final = frozenset(
    {
        "chmod",
        "chown",
        "cp",
        "install",
        "mkdir",
        "mv",
        "patch",
        "tee",
        "touch",
    },
)
DESTRUCTIVE_COMMANDS: Final = frozenset(
    {"dd", "mkfs", "rm", "rmdir", "shred", "truncate"}
)
EXTERNAL_COMMANDS: Final = frozenset(
    {
        "curl",
        "gh",
        "git",
        "hf",
        "npm",
        "pip",
        "pnpm",
        "poetry",
        "ssh",
        "uv",
        "uvx",
        "wget",
        "yarn",
    },
)
CREDENTIAL_COMMANDS: Final = frozenset(
    {"aws", "az", "gcloud", "op", "pass", "printenv", "security"}
)
PRODUCTION_COMMANDS: Final = frozenset(
    {"aws", "docker", "helm", "kubectl", "terraform"}
)
PAID_COMMANDS: Final = frozenset({"aws", "gcloud", "openai", "stripe"})
PRIVILEGE_COMMANDS: Final = frozenset({"doas", "su", "sudo"})
DEFAULT_ENV_ALLOWLIST: Final = ("PATH", "HOME", "TMPDIR")
DANGEROUS_ENV_NAMES: Final = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "OPENAI_API_KEY",
        "SLACK_BOT_TOKEN",
    },
)


class CommandExecutionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CommandExecutionRequest:
    command: str
    cwd: Path
    timeout_seconds: int
    approve_risk: bool = False
    allow_env: tuple[str, ...] = ()
    argv: tuple[str, ...] | None = None
    require_cwd_inside_project: bool = False
    project_root: Path | None = None
    approval_required_categories: tuple[CommandRiskCategory, ...] = (
        COMMAND_RISK_CATEGORIES
    )


@dataclass(frozen=True, slots=True)
class CommandRiskAssessment:
    categories: tuple[CommandRiskCategory, ...]
    approval_required: bool


@dataclass(frozen=True, slots=True)
class CommandEnvironment:
    values: dict[str, str]
    allowed: tuple[str, ...]
    blocked: tuple[str, ...]


def execute_shell_command(request: CommandExecutionRequest) -> CommandExecution:
    started = time.perf_counter()
    risk = assess_command_risk(
        request.command,
        approval_required_categories=request.approval_required_categories,
    )
    environment = _command_environment(request.allow_env)
    cwd = request.cwd.resolve()
    project_root = (request.project_root or Path.cwd()).resolve()
    cwd_inside_project = _is_relative_to(cwd, project_root)
    use_shell = request.argv is None
    if request.require_cwd_inside_project and not cwd_inside_project:
        return _contained_execution(
            request,
            risk,
            environment=environment,
            cwd=cwd,
        )
    if risk.approval_required and not request.approve_risk:
        return _blocked_execution(
            request,
            risk,
            environment=environment,
            cwd=cwd,
            cwd_inside_project=cwd_inside_project,
        )
    # When argv is provided the command runs without a shell, so metacharacters
    # are literal and no shell injection surface exists. Legacy command strings
    # still execute through the shell; risk and env/cwd metadata are recorded
    # either way so public users can audit the boundary.
    args: str | list[str] = request.command if use_shell else list(request.argv or ())
    try:
        completed = subprocess.run(  # noqa: S603
            args,
            cwd=cwd,
            env=environment.values,
            shell=use_shell,
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = _elapsed_ms(started)
        return CommandExecution(
            command=request.command,
            cwd=str(cwd),
            exit_code=124,
            stdout=_optional_text(exc.stdout),
            stderr=_optional_text(exc.stderr)
            or f"command timed out after {request.timeout_seconds} seconds",
            duration_ms=duration_ms,
            risk_categories=risk.categories,
            approval_required=risk.approval_required,
            approved=request.approve_risk and risk.approval_required,
            shell=use_shell,
            allowed_env=environment.allowed,
            blocked_env=environment.blocked,
            cwd_inside_project=cwd_inside_project,
        )
    except OSError as exc:
        raise CommandExecutionError(str(exc)) from exc

    return CommandExecution(
        command=request.command,
        cwd=str(cwd),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=_elapsed_ms(started),
        risk_categories=risk.categories,
        approval_required=risk.approval_required,
        approved=request.approve_risk and risk.approval_required,
        shell=use_shell,
        allowed_env=environment.allowed,
        blocked_env=environment.blocked,
        cwd_inside_project=cwd_inside_project,
    )


def assess_command_risk(
    command: str,
    *,
    approval_required_categories: tuple[CommandRiskCategory, ...] = (
        COMMAND_RISK_CATEGORIES
    ),
) -> CommandRiskAssessment:
    raw_tokens = _shell_tokens(command)
    categories: list[CommandRiskCategory] = []
    if raw_tokens and raw_tokens[0] in PRIVILEGE_COMMANDS:
        categories.append("privilege_escalation")
    # Classify the wrapped command so `sudo rm -rf` still reads as destructive.
    tokens = _strip_privilege_prefix(raw_tokens)
    first_token = tokens[0] if tokens else ""
    command_text = command.casefold()

    if first_token in WRITE_COMMANDS or _has_write_pattern(command_text, tokens):
        categories.append("write")
    if first_token in DESTRUCTIVE_COMMANDS or _has_destructive_pattern(tokens):
        categories.append("destructive")
    if first_token in EXTERNAL_COMMANDS or _has_external_pattern(command_text, tokens):
        categories.append("external_call")
    if first_token in CREDENTIAL_COMMANDS or _has_credential_pattern(
        command_text, tokens
    ):
        categories.append("credential_access")
    if first_token in PRODUCTION_COMMANDS and _has_production_pattern(tokens):
        categories.append("production_write")
    if first_token in PAID_COMMANDS and _has_paid_pattern(tokens):
        categories.append("paid_operation")

    unique_categories = tuple(dict.fromkeys(categories))
    required = set(approval_required_categories)
    return CommandRiskAssessment(
        categories=unique_categories,
        approval_required=any(category in required for category in unique_categories),
    )


def _blocked_execution(
    request: CommandExecutionRequest,
    risk: CommandRiskAssessment,
    *,
    environment: CommandEnvironment,
    cwd: Path,
    cwd_inside_project: bool,
) -> CommandExecution:
    categories = ", ".join(risk.categories)
    return CommandExecution(
        command=request.command,
        cwd=str(cwd),
        exit_code=126,
        stderr=f"command requires approval for risk categories: {categories}",
        duration_ms=0,
        risk_categories=risk.categories,
        approval_required=True,
        approved=False,
        shell=request.argv is None,
        allowed_env=environment.allowed,
        blocked_env=environment.blocked,
        cwd_inside_project=cwd_inside_project,
    )


def _contained_execution(
    request: CommandExecutionRequest,
    risk: CommandRiskAssessment,
    *,
    environment: CommandEnvironment,
    cwd: Path,
) -> CommandExecution:
    return CommandExecution(
        command=request.command,
        cwd=str(cwd),
        exit_code=126,
        stderr=f"command working directory escapes the project root: {cwd}",
        duration_ms=0,
        risk_categories=risk.categories,
        approval_required=risk.approval_required,
        approved=False,
        shell=request.argv is None,
        allowed_env=environment.allowed,
        blocked_env=environment.blocked,
        cwd_inside_project=False,
    )


def _command_environment(allow_env: tuple[str, ...]) -> CommandEnvironment:
    requested = _normalize_env_names(allow_env)
    names = (*DEFAULT_ENV_ALLOWLIST, *requested)
    values = {
        name: os.environ[name] for name in dict.fromkeys(names) if name in os.environ
    }
    blocked = tuple(
        name
        for name in sorted(DANGEROUS_ENV_NAMES)
        if name in os.environ and name not in requested
    )
    allowed = tuple(name for name in requested if name in values)
    return CommandEnvironment(values=values, allowed=allowed, blocked=blocked)


def _normalize_env_names(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(name for name in names if name))


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


_PRIVILEGE_FLAGS_WITH_VALUE: Final = frozenset({"--group", "--user", "-g", "-u"})


def _strip_privilege_prefix(tokens: tuple[str, ...]) -> tuple[str, ...]:
    remaining = tokens
    while remaining and remaining[0] in PRIVILEGE_COMMANDS:
        remaining = remaining[1:]
        # Skip wrapper flags (`sudo -u deploy ...`) to reach the real command.
        while remaining and remaining[0].startswith("-"):
            flag = remaining[0]
            remaining = remaining[1:]
            if flag in _PRIVILEGE_FLAGS_WITH_VALUE:
                remaining = remaining[1:]
    return remaining


def _shell_tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(token.casefold() for token in shlex.split(command))
    except ValueError:
        return tuple(command.casefold().split())


def _has_write_pattern(command_text: str, tokens: tuple[str, ...]) -> bool:
    return (
        _has_file_redirection(command_text)
        or "-i" in tokens
        or ("git" in tokens[:1] and _second_token_is(tokens, {"add", "commit"}))
    )


def _has_file_redirection(command_text: str) -> bool:
    normalized = command_text
    for standard_stream in ("2>&1", "1>&2", ">&1", ">&2"):
        normalized = normalized.replace(standard_stream, "")
    return ">" in normalized


def _has_destructive_pattern(tokens: tuple[str, ...]) -> bool:
    return (
        ("git" in tokens[:1] and _second_token_is(tokens, {"clean", "reset"}))
        or ("docker" in tokens[:1] and _second_token_is(tokens, {"rm", "rmi"}))
        or ("kubectl" in tokens[:1] and _second_token_is(tokens, {"delete"}))
        or ("terraform" in tokens[:1] and _second_token_is(tokens, {"destroy"}))
    )


def _has_external_pattern(command_text: str, tokens: tuple[str, ...]) -> bool:
    return (
        "http://" in command_text
        or "https://" in command_text
        or ("git" in tokens[:1] and _second_token_is(tokens, {"fetch", "pull", "push"}))
        or ("gh" in tokens[:1] and _second_token_is(tokens, {"api", "pr", "issue"}))
    )


def _has_credential_pattern(command_text: str, tokens: tuple[str, ...]) -> bool:
    credential_markers = (
        ".env",
        "api_key",
        "password",
        "secret",
        "token",
    )
    return any(marker in command_text for marker in credential_markers) or (
        "cat" in tokens[:1] and any(token.endswith(".env") for token in tokens)
    )


def _has_production_pattern(tokens: tuple[str, ...]) -> bool:
    return (
        ("aws" in tokens[:1] and _second_token_is(tokens, {"s3", "ec2", "lambda"}))
        or ("docker" in tokens[:1] and _second_token_is(tokens, {"push"}))
        or ("helm" in tokens[:1] and _second_token_is(tokens, {"install", "upgrade"}))
        or ("kubectl" in tokens[:1] and _second_token_is(tokens, {"apply", "delete"}))
        or ("terraform" in tokens[:1] and _second_token_is(tokens, {"apply"}))
    )


def _has_paid_pattern(tokens: tuple[str, ...]) -> bool:
    return (
        ("aws" in tokens[:1] and _second_token_is(tokens, {"bedrock", "sagemaker"}))
        or ("gcloud" in tokens[:1] and _second_token_is(tokens, {"ai"}))
        or ("openai" in tokens[:1] and _second_token_is(tokens, {"api"}))
        or "stripe" in tokens[:1]
    )


def _second_token_is(tokens: tuple[str, ...], values: set[str]) -> bool:
    return len(tokens) > 1 and tokens[1] in values


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _optional_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
