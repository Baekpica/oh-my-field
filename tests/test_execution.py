import shlex
import sys
from pathlib import Path

import pytest

from oh_my_field.execution import (
    DANGEROUS_ENV_NAMES,
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


def test_assess_command_risk_flags_privilege_escalation() -> None:
    assert assess_command_risk("sudo systemctl restart nginx").categories == (
        "privilege_escalation",
    )
    assert assess_command_risk("doas reboot").categories == ("privilege_escalation",)


def test_assess_command_risk_classifies_command_wrapped_by_sudo() -> None:
    assert assess_command_risk("sudo rm -rf /var/data").categories == (
        "privilege_escalation",
        "destructive",
    )
    assert assess_command_risk("sudo -u deploy rm -rf /var/data").categories == (
        "privilege_escalation",
        "destructive",
    )


def test_execute_shell_command_blocks_privilege_escalation_without_approval(
    tmp_path: Path,
) -> None:
    execution = execute_shell_command(
        CommandExecutionRequest(
            command="sudo printf ok",
            cwd=tmp_path,
            timeout_seconds=5,
        ),
    )

    assert execution.exit_code == 126
    assert execution.risk_categories == ("privilege_escalation",)
    assert execution.approval_required is True
    assert execution.approved is False
    assert "privilege_escalation" in execution.stderr


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
    for name in DANGEROUS_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
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


def test_execute_command_argv_treats_metacharacters_literally(
    tmp_path: Path,
) -> None:
    redirect_target = tmp_path / "redirected.txt"
    argv = (
        sys.executable,
        "-c",
        "import sys; print(sys.argv[1:])",
        ">",
        str(redirect_target),
    )

    execution = execute_shell_command(
        CommandExecutionRequest(
            command=shlex.join(argv),
            argv=argv,
            cwd=tmp_path,
            timeout_seconds=10,
            approve_risk=True,
        ),
    )

    assert execution.exit_code == 0
    assert execution.shell is False
    assert not redirect_target.exists()
    assert ">" in execution.stdout


def test_execute_command_blocks_cwd_outside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    execution = execute_shell_command(
        CommandExecutionRequest(
            command="printf ok",
            cwd=outside,
            timeout_seconds=5,
            project_root=project_root,
            require_cwd_inside_project=True,
        ),
    )

    assert execution.exit_code == 126
    assert execution.shell is True
    assert execution.cwd_inside_project is False
    assert execution.stdout == ""
    assert "escapes the project root" in execution.stderr


def _env_probe_command(name: str) -> str:
    return (
        f"{shlex.quote(sys.executable)} -c "
        f'\'import os; print(os.getenv("{name}", "missing"))\''
    )
