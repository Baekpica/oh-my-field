from pathlib import Path

from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.application.runtimes import (
    RuntimeInventoryRequest,
    run_runtime_inventory_workflow,
)
from oh_my_field.application.runtimes.workflow import RUNTIME_NAMES
from oh_my_field.domain.skill.models import SkillInstallRequest
from oh_my_field.mcp.schemas import McpInstallRequest


def test_inventory_lists_all_runtimes_when_nothing_installed(tmp_path: Path) -> None:
    summary = run_runtime_inventory_workflow(
        RuntimeInventoryRequest(home=tmp_path, project=tmp_path / "project"),
    )

    assert tuple(state.runtime for state in summary.runtimes) == RUNTIME_NAMES
    assert summary.ready_count == 0
    for state in summary.runtimes:
        assert state.skill_installed is False
        assert state.mcp_installed is False
        assert state.overall_status in ("absent", "partial")


def test_inventory_flips_runtime_when_skill_and_mcp_installed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    # Make the runtime itself look present locally.
    (home / ".claude").mkdir()

    install_omf_skill(
        SkillInstallRequest(runtime="claude_code", home=home, project=project),
    )
    install_mcp_config(
        McpInstallRequest(client="claude_code", home=home, project=project),
    )

    summary = run_runtime_inventory_workflow(
        RuntimeInventoryRequest(home=home, project=project),
    )
    claude = next(s for s in summary.runtimes if s.runtime == "claude_code")

    assert claude.skill_installed is True
    assert claude.mcp_installed is True
    assert claude.presence == "present"
    assert claude.overall_status == "ready"
    assert summary.ready_count == 1


def test_inventory_marks_runtime_present_from_config_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()

    summary = run_runtime_inventory_workflow(
        RuntimeInventoryRequest(home=home, project=tmp_path / "project"),
    )
    codex = next(s for s in summary.runtimes if s.runtime == "codex")

    assert codex.presence == "present"
    # Present but no skill/MCP yet -> partial, with an actionable next step.
    assert codex.overall_status == "partial"
    assert codex.next_action
