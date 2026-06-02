from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner, Result

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    HarnessStatus,
    PromotionCriteria,
    ReplayRecord,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_evidence, write_manifest, write_replay


class EvalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_id: str
    eval_path: str
    capability_name: str
    status: str


def invoke_eval(
    *args: str,
    tmp_path: Path,
    capabilities_dir: Path | None = None,
    evidence_dir: Path | None = None,
    replay_dir: Path | None = None,
    eval_dir: Path | None = None,
) -> Result:
    capabilities_dir = capabilities_dir or (tmp_path / "capabilities")
    evidence_dir = evidence_dir or (tmp_path / "evidence")
    replay_dir = replay_dir or (tmp_path / "replays")
    eval_dir = eval_dir or (tmp_path / "evals")
    return CliRunner().invoke(
        app,
        [
            "eval",
            *args,
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--replay-dir",
            str(replay_dir),
            "--eval-dir",
            str(eval_dir),
        ],
    )


def make_evidence_record(
    harness_status: HarnessStatus = "pass",
) -> EvidenceRecord:
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
            status=harness_status,
            checks=("files_readable", "schema_valid"),
            failures=() if harness_status == "pass" else ("schema_invalid",),
        ),
    )


def make_manifest(
    capability_name: str = "repo_issue_triage",
) -> CapabilityManifest:
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


def make_replay_record(
    capability_name: str = "repo_issue_triage",
    harness_status: HarnessStatus = "pass",
) -> ReplayRecord:
    return ReplayRecord(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name=capability_name,
        source_evidence_id="20260602T010203Z-deadbeef",
        source_goal="triage repo issue",
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("load_manifest", "load_source_evidence", "build_replay"),
        ),
        harness=HarnessResult(
            status=harness_status,
            checks=("schema_valid",),
            failures=() if harness_status == "pass" else ("schema_invalid",),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
    )


def test_eval_creates_eval_result_from_manifest_evidence_and_replay(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    replay_dir = tmp_path / "replays"
    eval_dir = tmp_path / "evals"
    evidence = make_evidence_record()
    manifest = make_manifest()
    replay = make_replay_record()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)
    write_replay(replay, replay_dir)

    result = invoke_eval(
        manifest.name,
        "--replay-id",
        replay.id,
        tmp_path=tmp_path,
        capabilities_dir=capabilities_dir,
        evidence_dir=evidence_dir,
        replay_dir=replay_dir,
        eval_dir=eval_dir,
    )

    assert result.exit_code == 0
    output = EvalOutput.model_validate_json(result.stdout)
    eval_path = Path(output.eval_path)
    eval_result = EvalResult.model_validate_json(eval_path.read_text(encoding="utf-8"))
    assert eval_path.exists()
    assert output.status == "pass"
    assert eval_result.replay_id == replay.id
    assert eval_result.status == "pass"
    assert {check.name for check in eval_result.checks} == {
        "manifest_loaded",
        "source_evidence_loaded",
        "source_harness_pass",
        "replay_loaded",
        "replay_matches_capability",
        "replay_matches_source_evidence",
        "replay_harness_pass",
    }


def test_eval_without_replay_id_uses_manifest_and_source_evidence_only(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = invoke_eval(manifest.name, tmp_path=tmp_path)

    assert result.exit_code == 0
    output = EvalOutput.model_validate_json(result.stdout)
    eval_result = EvalResult.model_validate_json(
        Path(output.eval_path).read_text(encoding="utf-8"),
    )
    assert output.status == "pass"
    assert eval_result.replay_id is None
    assert {check.name for check in eval_result.checks} == {
        "manifest_loaded",
        "source_evidence_loaded",
        "source_harness_pass",
    }


def test_eval_runs_harness_commands_and_records_failures(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = invoke_eval(
        manifest.name,
        "--harness-command",
        "false",
        "--command-cwd",
        str(tmp_path),
        tmp_path=tmp_path,
    )

    assert result.exit_code == 0
    output = EvalOutput.model_validate_json(result.stdout)
    eval_result = EvalResult.model_validate_json(
        Path(output.eval_path).read_text(encoding="utf-8"),
    )
    assert output.status == "fail"
    assert eval_result.command_executions[0].exit_code == 1
    assert "harness_command_1" in {check.name for check in eval_result.checks}


def test_eval_records_checklist_and_rubric_harness_results(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = invoke_eval(
        manifest.name,
        "--checklist-pass",
        "schema includes reviewer",
        "--checklist-fail",
        "approval attached",
        "--rubric-score",
        "clarity:2:5:3:needs clearer evidence",
        tmp_path=tmp_path,
    )

    assert result.exit_code == 0
    output = EvalOutput.model_validate_json(result.stdout)
    eval_result = EvalResult.model_validate_json(
        Path(output.eval_path).read_text(encoding="utf-8"),
    )
    assert output.status == "fail"
    assert [item.status for item in eval_result.checklist_items] == ["pass", "fail"]
    assert eval_result.rubric_scores[0].status == "fail"
    assert "checklist_2_approval_attached" in {
        check.name for check in eval_result.checks
    }
    assert "rubric_1_clarity" in {check.name for check in eval_result.checks}


def test_eval_fails_for_missing_manifest(tmp_path: Path) -> None:
    result = invoke_eval("repo_issue_triage", tmp_path=tmp_path)

    assert result.exit_code != 0
    assert "not found" in result.stderr


def test_eval_fails_for_missing_replay_when_requested(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    write_evidence(make_evidence_record(), evidence_dir)
    write_manifest(make_manifest(), capabilities_dir)

    result = invoke_eval(
        "repo_issue_triage",
        "--replay-id",
        "20260602T010204Z-feedface",
        tmp_path=tmp_path,
    )

    assert result.exit_code != 0
    assert "not found" in result.stderr


def test_eval_rejects_invalid_replay_id(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    write_evidence(make_evidence_record(), evidence_dir)
    write_manifest(make_manifest(), capabilities_dir)

    result = invoke_eval(
        "repo_issue_triage",
        "--replay-id",
        "../bad",
        tmp_path=tmp_path,
    )

    assert result.exit_code != 0
    assert "pattern" in result.stderr or "string_pattern_mismatch" in result.stderr


def test_eval_rejects_invalid_capability_name(tmp_path: Path) -> None:
    result = invoke_eval("../bad", tmp_path=tmp_path)

    assert result.exit_code != 0
    assert "pattern" in result.stderr or "string_pattern_mismatch" in result.stderr
