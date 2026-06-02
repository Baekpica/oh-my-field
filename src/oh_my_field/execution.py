import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from oh_my_field.models import CommandExecution


class CommandExecutionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CommandExecutionRequest:
    command: str
    cwd: Path
    timeout_seconds: int


def execute_shell_command(request: CommandExecutionRequest) -> CommandExecution:
    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S602
            request.command,
            cwd=request.cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = _elapsed_ms(started)
        return CommandExecution(
            command=request.command,
            cwd=str(request.cwd),
            exit_code=124,
            stdout=_optional_text(exc.stdout),
            stderr=_optional_text(exc.stderr)
            or f"command timed out after {request.timeout_seconds} seconds",
            duration_ms=duration_ms,
        )
    except OSError as exc:
        raise CommandExecutionError(str(exc)) from exc

    return CommandExecution(
        command=request.command,
        cwd=str(request.cwd),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _optional_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
