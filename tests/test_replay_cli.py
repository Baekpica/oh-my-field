from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import load_replay, write_evidence, write_manifest


class ReplayOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    replay_id: str
    replay_path: str
    capability_name: str
    harness_status: str


class ReplayMatrixItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_profile: str
    replay_id: str
    replay_path: str
    harness_status: str


class ReplayMatrixOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    results: tuple[ReplayMatrixItemOutput, ...]


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="0" * 64,
            ),
        ),
        feedback=(),
        harness=HarnessResult(
            status="pass",
            checks=("files_readable", "schema_valid"),
            failures=(),
        ),
    )


def make_manifest(capability_name: str = "repo_issue_triage") -> CapabilityManifest:
    return CapabilityManifest(
        name=capability_name,
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("load_evidence", "write_capability"),
        ),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid",),
            failures=(),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def test_replay_creates_replay_record_from_manifest_and_evidence(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    replay_dir = tmp_path / "replays"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "replay",
            manifest.name,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(replay_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReplayOutput.model_validate_json(result.stdout)
    replay_path = Path(output.replay_path)
    replay = load_replay(output.replay_id, replay_dir)
    assert replay_path.exists()
    assert replay.capability_name == manifest.name
    assert replay.source_evidence_id == evidence.id
    assert replay.source_goal == evidence.goal
    assert replay.harness.status == output.harness_status
    assert replay.harness == evidence.harness
    assert replay.runtime == evidence.runtime


def test_replay_execute_reruns_stored_commands(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    replay_dir = tmp_path / "replays"
    evidence = make_evidence_record().model_copy(
        update={"generated_commands": ("printf replayed",)},
    )
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "replay",
            manifest.name,
            "--execute",
            "--command-cwd",
            str(tmp_path),
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(replay_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReplayOutput.model_validate_json(result.stdout)
    replay = load_replay(output.replay_id, replay_dir)
    assert replay.command_executions[0].stdout == "replayed"
    assert replay.harness.status == "pass"
    assert "commands_replayed" in replay.harness.checks


def test_replay_matrix_creates_runtime_profile_replays(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    replay_dir = tmp_path / "replays"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "replay",
            manifest.name,
            "--matrix",
            "codex,claude_code,hermes",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(replay_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReplayMatrixOutput.model_validate_json(result.stdout)
    assert [item.runtime_profile for item in output.results] == [
        "codex",
        "claude_code",
        "hermes",
    ]
    for item in output.results:
        replay = load_replay(item.replay_id, replay_dir)
        assert replay.runtime_profile == item.runtime_profile
        assert replay.runtime.name == item.runtime_profile
        assert replay.integrity_chain[-1].artifact_type == "replay"


def test_replay_blocks_risky_stored_command_without_approval(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    replay_dir = tmp_path / "replays"
    marker_path = tmp_path / "blocked-replay.txt"
    evidence = make_evidence_record().model_copy(
        update={"generated_commands": (f"touch {marker_path}",)},
    )
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "replay",
            manifest.name,
            "--execute",
            "--command-cwd",
            str(tmp_path),
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(replay_dir),
        ],
    )

    assert result.exit_code == 0
    assert not marker_path.exists()
    output = ReplayOutput.model_validate_json(result.stdout)
    replay = load_replay(output.replay_id, replay_dir)
    execution = replay.command_executions[0]
    assert output.harness_status == "fail"
    assert execution.exit_code == 126
    assert execution.risk_categories == ("write",)
    assert execution.approval_required
    assert not execution.approved


def test_replay_fails_for_missing_manifest(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "repo_issue_triage",
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--replay-dir",
            str(tmp_path / "replays"),
        ],
    )

    assert result.exit_code != 0
    assert "not found" in result.stderr


def test_replay_rejects_invalid_capability_name(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "../bad",
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--replay-dir",
            str(tmp_path / "replays"),
        ],
    )

    assert result.exit_code != 0
    assert "pattern" in result.stderr or "string_pattern_mismatch" in result.stderr


def test_replay_fails_for_missing_source_evidence(tmp_path: Path) -> None:
    capabilities_dir = tmp_path / "capabilities"
    write_manifest(make_manifest(), capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "replay",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--replay-dir",
            str(tmp_path / "replays"),
        ],
    )

    assert result.exit_code != 0
    assert "not found" in result.stderr


def test_replay_rejects_manifest_name_mismatch(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    write_evidence(make_evidence_record(), evidence_dir)
    mismatch_dir = capabilities_dir / "repo_issue_triage"
    mismatch_dir.mkdir(parents=True)
    mismatch_dir.joinpath("manifest.yaml").write_text(
        (
            "name: other_capability\n"
            "version: 0.1.0\n"
            "description: GitHub issue triage capability\n"
            "status: candidate\n"
            "source_evidence_id: 20260602T010203Z-deadbeef\n"
            "normalized_goal: triage repo issue\n"
            "inputs:\n"
            "  - goal\n"
            "workflow:\n"
            "  graph: langgraph\n"
            "  nodes:\n"
            "    - load_evidence\n"
            "    - write_capability\n"
            "harness:\n"
            "  status: pass\n"
            "  checks:\n"
            "    - schema_valid\n"
            "  failures: []\n"
            "runtime:\n"
            "  name: codex\n"
            "  model: gpt-5.5\n"
            "promotion_criteria:\n"
            "  min_success_runs: 3\n"
            "  max_human_intervention_rate: 0.3\n"
            "  required_harness_pass_rate: 0.9\n"
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "replay",
            "repo_issue_triage",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(tmp_path / "replays"),
        ],
    )

    assert result.exit_code != 0
    assert "does not match requested capability" in result.stderr
