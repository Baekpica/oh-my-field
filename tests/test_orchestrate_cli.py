from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
    WorkflowNodeResult,
    WorkflowRunConfig,
    WorkflowRunRecord,
)
from oh_my_field.storage import (
    load_workflow_run,
    write_evidence,
    write_manifest,
    write_workflow_run,
)


class WorkflowOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    run_path: str
    status: str
    current_node: str | None
    evidence_id: str | None = None
    capability_name: str | None = None
    replay_id: str | None = None
    eval_id: str | None = None
    context_id: str | None = None
    learning_id: str | None = None
    failure_reason: str | None = None


def test_run_executes_full_workflow_and_writes_checkpoints(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Find the bug.", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--goal",
            "triage repo issue",
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--prompt",
            str(prompt_path),
            "--command",
            "printf orchestrated",
            "--harness-command",
            "printf harness",
            "--checklist-pass",
            "operator rubric attached",
            "--rubric-score",
            "quality:4:5:3:usable",
            "--runtime-tool",
            "shell",
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--capabilities-dir",
            str(tmp_path / "capabilities"),
            "--replay-dir",
            str(tmp_path / "replays"),
            "--eval-dir",
            str(tmp_path / "evals"),
            "--context-dir",
            str(tmp_path / "context"),
            "--learning-dir",
            str(tmp_path / "learning"),
            "--workflow-dir",
            str(tmp_path / "workflows"),
        ],
    )

    assert result.exit_code == 0
    output = WorkflowOutput.model_validate_json(result.stdout)
    record = load_workflow_run(output.run_id, tmp_path / "workflows")
    assert output.status == "completed"
    assert record.completed_nodes == (
        "import_evidence",
        "promote_capability",
        "pack_context",
        "run_verification",
        "evaluate_capability",
        "record_learning_patch",
    )
    assert record.evidence_id is not None
    assert record.capability_name == "repo_issue_triage"
    assert record.replay_id is not None
    assert record.eval_id is not None
    assert record.context_id is not None
    assert record.learning_id is not None
    assert Path(output.run_path).exists()
    eval_result = EvalResult.model_validate_json(
        (tmp_path / "evals" / f"{record.eval_id}.json").read_text(
            encoding="utf-8",
        ),
    )
    assert eval_result.checklist_items[0].name == "operator rubric attached"
    assert eval_result.rubric_scores[0].status == "pass"


def test_resume_continues_from_saved_checkpoint(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    workflow_dir = tmp_path / "workflows"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)
    run = WorkflowRunRecord(
        id="20260602T010208Z-1234abcd",
        created_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        goal=evidence.goal,
        status="running",
        current_node="execute_replay",
        completed_nodes=(
            "observe_capture",
            "structure_promote",
            "context_pack",
        ),
        config=WorkflowRunConfig(
            capability_name=manifest.name,
            description=manifest.description,
            version=manifest.version,
            field=evidence.field,
            runtime=evidence.runtime.name,
            model=evidence.runtime.model,
            command_cwd=str(tmp_path),
            command_timeout_seconds=60,
            evidence_dir=str(evidence_dir),
            capabilities_dir=str(capabilities_dir),
            replay_dir=str(tmp_path / "replays"),
            eval_dir=str(tmp_path / "evals"),
            context_dir=str(tmp_path / "context"),
            learning_dir=str(tmp_path / "learning"),
        ),
        nodes=(
            WorkflowNodeResult(
                name="observe_capture",
                status="pass",
                message="captured",
            ),
            WorkflowNodeResult(
                name="structure_promote",
                status="pass",
                message="promoted",
            ),
            WorkflowNodeResult(
                name="context_pack",
                status="pass",
                message="packed",
            ),
        ),
        evidence_id=evidence.id,
        capability_name=manifest.name,
        context_id="20260602T010209Z-abcdef12",
    )
    write_workflow_run(run, workflow_dir)

    result = CliRunner().invoke(
        app,
        [
            "resume",
            run.id,
            "--workflow-dir",
            str(workflow_dir),
        ],
    )

    assert result.exit_code == 0
    output = WorkflowOutput.model_validate_json(result.stdout)
    record = load_workflow_run(output.run_id, workflow_dir)
    assert output.status == "completed"
    assert record.completed_nodes[-3:] == (
        "run_verification",
        "evaluate_capability",
        "record_learning_patch",
    )


def test_status_reads_workflow_checkpoint(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "workflows"
    run = WorkflowRunRecord(
        id="20260602T010208Z-1234abcd",
        created_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        goal="triage repo issue",
        status="running",
        current_node="evaluate_capability",
        config=WorkflowRunConfig(
            capability_name="repo_issue_triage",
            description="GitHub issue triage capability",
            version="0.1.0",
            field="local",
            runtime="codex",
            command_cwd=str(tmp_path),
            command_timeout_seconds=60,
            evidence_dir=str(tmp_path / "evidence"),
            capabilities_dir=str(tmp_path / "capabilities"),
            replay_dir=str(tmp_path / "replays"),
            eval_dir=str(tmp_path / "evals"),
            context_dir=str(tmp_path / "context"),
            learning_dir=str(tmp_path / "learning"),
        ),
    )
    write_workflow_run(run, workflow_dir)

    result = CliRunner().invoke(
        app,
        ["status", run.id, "--workflow-dir", str(workflow_dir)],
    )

    assert result.exit_code == 0
    output = WorkflowOutput.model_validate_json(result.stdout)
    assert output.status == "running"
    assert output.current_node == "evaluate_capability"


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
    )


def make_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        source_evidence_id="20260602T010203Z-deadbeef",
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=("import_evidence",)),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )
