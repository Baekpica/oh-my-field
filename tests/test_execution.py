import shlex
import sys
from pathlib import Path

import pytest

from oh_my_field.execution import (
    CommandExecutionRequest,
    assess_command_risk,
    execute_shell_command,
)


def test_assess_command_risk_classifies_representative_patterns() -> None:
    assert assess_command_risk("rm -rf build").categories == ("destructive",)
    assert assess_command_risk("curl https://example.test").categories == (
        "external_call",
    )
    assert assess_command_risk("cat .env").categories == ("credential_access",)


def test_assess_command_risk_honors_required_category_policy() -> None:
    risk = assess_command_risk(
        "touch output.txt",
        approval_required_categories=("destructive",),
    )

    assert risk.categories == ("write",)
    assert not risk.approval_required


def test_execute_shell_command_uses_minimal_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMF_TEST_TOKEN", "secret")

    execution = execute_shell_command(
        CommandExecutionRequest(
            command=_env_probe_command("OMF_TEST_TOKEN"),
            cwd=tmp_path,
            timeout_seconds=5,
            approve_risk=True,
        ),
    )

    assert execution.exit_code == 0
    assert execution.stdout == "missing\n"
    assert execution.env_policy == "minimal"
    assert execution.allowed_env == ()


def test_execute_shell_command_allows_explicit_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMF_TEST_TOKEN", "secret")

    execution = execute_shell_command(
        CommandExecutionRequest(
            command=_env_probe_command("OMF_TEST_TOKEN"),
            cwd=tmp_path,
            timeout_seconds=5,
            allow_env=("OMF_TEST_TOKEN",),
            approve_risk=True,
        ),
    )

    assert execution.exit_code == 0
    assert execution.stdout == "secret\n"
    assert execution.allowed_env == ("OMF_TEST_TOKEN",)


def test_execute_shell_command_records_blocked_dangerous_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    execution = execute_shell_command(
        CommandExecutionRequest(
            command="printf ok",
            cwd=tmp_path,
            timeout_seconds=5,
        ),
    )

    assert execution.exit_code == 0
    assert execution.stdout == "ok"
    assert execution.blocked_env == ("OPENAI_API_KEY",)


def test_execute_shell_command_records_timeout(tmp_path: Path) -> None:
    execution = execute_shell_command(
        CommandExecutionRequest(
            command=(f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(2)'"),
            cwd=tmp_path,
            timeout_seconds=1,
        ),
    )

    assert execution.exit_code == 124
    assert "command timed out after 1 seconds" in execution.stderr


def _env_probe_command(name: str) -> str:
    return (
        f"{shlex.quote(sys.executable)} -c "
        f'\'import os; print(os.getenv("{name}", "missing"))\''
    )
