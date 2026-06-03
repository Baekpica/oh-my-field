from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.dashboard import (
    DashboardPaths,
    DashboardReviewRequest,
    DashboardSnapshot,
    build_dashboard_snapshot,
    dashboard_html,
    record_dashboard_review,
)
from oh_my_field.models import (
    CapabilityManifest,
    CommandExecution,
    EvalCase,
    EvalCheck,
    EvalResult,
    EvalSet,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    PromotionMetrics,
    RuntimeInfo,
    WorkflowManifest,
    WorkflowNodeResult,
    WorkflowRunConfig,
    WorkflowRunRecord,
)
from oh_my_field.storage import (
    write_eval_result,
    write_eval_set,
    write_evidence,
    write_manifest,
    write_workflow_run,
)


def test_dashboard_snapshot_surfaces_runtime_state_and_approvals(
    tmp_path: Path,
) -> None:
    paths = make_dashboard_paths(tmp_path)
    evidence = make_evidence_record(tmp_path)
    eval_result = make_eval_result(evidence.id, tmp_path)
    eval_set = EvalSet(
        name="repo_issue_regression",
        version="0.1.0",
        capability_name="repo_issue_triage",
        cases=(EvalCase(id="blocked_external_call"),),
    )
    manifest = make_manifest(evidence.id, eval_result.id)
    workflow = make_workflow_record(evidence.id, eval_result.id, tmp_path)
    write_evidence(evidence, paths.evidence_dir)
    write_eval_result(eval_result, paths.eval_dir)
    write_eval_set(eval_set, paths.eval_set_dir)
    write_manifest(manifest, paths.capabilities_dir)
    write_workflow_run(workflow, paths.workflow_dir)

    snapshot = build_dashboard_snapshot(paths)

    assert snapshot.metrics.workflow_count == 1
    assert snapshot.metrics.pending_review_count == 1
    assert snapshot.metrics.pending_approval_count == 1
    assert snapshot.metrics.regression_case_count == 1
    assert snapshot.metrics.user_intervention_count == 1
    assert snapshot.workflows[0].current_node == "execute_replay"
    assert snapshot.workflows[0].nodes[3].status == "running"
    assert snapshot.workflows[0].pending_approval_count == 1
    assert snapshot.approvals[0].target_type == "evidence"
    assert snapshot.approvals[0].risk_categories == ("external_call",)
    assert snapshot.capabilities[0].network_policy == "disabled"
    assert snapshot.capabilities[0].eval_count == 1
    assert snapshot.capabilities[0].pass_rate == 0.0
    assert snapshot.capabilities[0].promotion_success_runs == 2
    assert snapshot.capabilities[0].promotion_harness_pass_rate == 0.67
    assert snapshot.capabilities[0].promotion_eval_pass_rate == 0.0
    assert not snapshot.capabilities[0].promotion_criteria_met
    assert snapshot.capabilities[0].integrity_status == "fail"
    assert snapshot.capabilities[0].next_action == (
        "run `omf verify capability repo_issue_triage`"
    )
    assert snapshot.comparisons[0].capability_name == "repo_issue_triage"
    assert snapshot.comparisons[0].eval_count == 1
    assert {action.kind for action in snapshot.console_actions} == {
        "review",
        "regression_case",
    }
    assert {event.kind for event in snapshot.events} >= {
        "approval_required",
        "pending_review",
    }


def test_dashboard_once_outputs_snapshot_json(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "dashboard",
            "--once",
            "--capabilities-dir",
            str(paths.capabilities_dir),
            "--evidence-dir",
            str(paths.evidence_dir),
            "--replay-dir",
            str(paths.replay_dir),
            "--eval-dir",
            str(paths.eval_dir),
            "--workflow-dir",
            str(paths.workflow_dir),
            "--review-dir",
            str(paths.review_dir),
            "--eval-set-dir",
            str(paths.eval_set_dir),
            "--learning-patch-dir",
            str(paths.learning_patch_dir),
        ],
    )

    assert result.exit_code == 0
    snapshot = DashboardSnapshot.model_validate_json(result.stdout)
    assert snapshot.metrics.workflow_count == 0
    assert "/api/snapshot" in dashboard_html()
    assert "workflow-rows" in dashboard_html()


def test_dashboard_review_records_decision_and_clears_pending_approval(
    tmp_path: Path,
) -> None:
    paths = make_dashboard_paths(tmp_path)
    evidence = make_evidence_record(tmp_path)
    write_evidence(evidence, paths.evidence_dir)

    before = build_dashboard_snapshot(paths)
    review_json = record_dashboard_review(
        DashboardReviewRequest(
            target_type="evidence",
            target_id=evidence.id,
            action="approve",
            reviewer="operator",
            notes=("approved from dashboard",),
        ),
        paths,
    )
    after = build_dashboard_snapshot(paths)

    assert before.metrics.pending_approval_count == 1
    assert after.metrics.pending_approval_count == 0
    assert after.reviews[0].status == "approved"
    assert "approved" in review_json


def make_dashboard_paths(tmp_path: Path) -> DashboardPaths:
    return DashboardPaths(
        capabilities_dir=tmp_path / "capabilities",
        evidence_dir=tmp_path / "evidence",
        replay_dir=tmp_path / "replays",
        eval_dir=tmp_path / "evals",
        workflow_dir=tmp_path / "workflows",
        review_dir=tmp_path / "reviews",
        eval_set_dir=tmp_path / "eval_sets",
        learning_patch_dir=tmp_path / "learning_patches",
    )


def make_evidence_record(tmp_path: Path) -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5", tools=("shell",)),
        command_executions=(
            CommandExecution(
                command="curl https://example.com",
                cwd=str(tmp_path),
                exit_code=1,
                duration_ms=12,
                risk_categories=("external_call",),
                approval_required=True,
                approved=False,
            ),
        ),
        user_interventions=("blocked external call",),
        harness=HarnessResult(
            status="fail",
            checks=("command_blocked",),
            failures=("approval_required",),
        ),
    )


def make_eval_result(evidence_id: str, tmp_path: Path) -> EvalResult:
    return EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id=evidence_id,
        status="fail",
        checks=(
            EvalCheck(
                name="approval_required",
                status="fail",
                message="external call blocked",
            ),
        ),
        failures=("approval_required",),
        command_executions=(
            CommandExecution(
                command="uv run pytest",
                cwd=str(tmp_path),
                exit_code=0,
                duration_ms=34,
            ),
        ),
    )


def make_manifest(evidence_id: str, eval_id: str) -> CapabilityManifest:
    return CapabilityManifest(
        name="repo_issue_triage",
        version="0.1.0",
        description="GitHub issue triage capability",
        status="candidate",
        evaluation_results=(eval_id,),
        source_evidence_id=evidence_id,
        normalized_goal="triage repo issue",
        inputs=("goal",),
        workflow=WorkflowManifest(
            graph="langgraph",
            nodes=("parse_goal", "run_harness"),
        ),
        harness=HarnessResult(
            status="pass",
            checks=("schema_valid",),
            required_checks=("pytest",),
        ),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5", tools=("shell",)),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
        promotion_metrics=PromotionMetrics(
            evidence_count=3,
            successful_evidence_count=2,
            failed_evidence_count=1,
            harness_pass_rate=0.67,
            human_intervention_rate=0.33,
            retry_rate=0.0,
            eval_count=1,
            eval_pass_rate=0.0,
            runtime_profiles=("runtime:codex",),
            criteria_met=False,
            eval_gate_met=False,
        ),
    )


def make_workflow_record(
    evidence_id: str,
    eval_id: str,
    tmp_path: Path,
) -> WorkflowRunRecord:
    return WorkflowRunRecord(
        id="20260602T010205Z-1234abcd",
        created_at=datetime(2026, 6, 2, 1, 2, 5, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 2, 7, tzinfo=UTC),
        goal="triage repo issue",
        status="pending_review",
        current_node="execute_replay",
        completed_nodes=("observe_capture", "structure_promote", "context_pack"),
        config=WorkflowRunConfig(
            capability_name="repo_issue_triage",
            description="GitHub issue triage capability",
            version="0.1.0",
            field="local",
            runtime="codex",
            model="gpt-5.5",
            runtime_tools=("shell",),
            commands=("curl https://example.com",),
            command_cwd=str(tmp_path),
            command_timeout_seconds=60,
            harness_commands=("uv run pytest",),
            evidence_dir=str(tmp_path / "evidence"),
            capabilities_dir=str(tmp_path / "capabilities"),
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
        evidence_id=evidence_id,
        capability_name="repo_issue_triage",
        eval_id=eval_id,
    )
