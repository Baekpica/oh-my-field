import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.dashboard import (
    DashboardHTTPServer,
    DashboardPaths,
    DashboardReviewRequest,
    DashboardServeRequest,
    DashboardSnapshot,
    build_dashboard_snapshot,
    create_dashboard_server,
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
    LearningPatchDecision,
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
    write_learning_patch_decision,
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
    learning_patch = make_learning_patch()
    write_evidence(evidence, paths.evidence_dir)
    write_eval_result(eval_result, paths.eval_dir)
    write_eval_set(eval_set, paths.eval_set_dir)
    write_manifest(manifest, paths.capabilities_dir)
    write_portability_status(paths.capabilities_dir / manifest.name)
    write_learning_patch_decision(learning_patch, paths.learning_patch_dir)
    write_workflow_run(workflow, paths.workflow_dir)

    snapshot = build_dashboard_snapshot(paths)

    assert snapshot.metrics.workflow_count == 1
    assert snapshot.metrics.pending_review_count == 1
    assert snapshot.metrics.pending_approval_count == 1
    assert snapshot.metrics.regression_case_count == 1
    assert snapshot.metrics.learning_patch_count == 1
    assert snapshot.metrics.user_intervention_count == 1
    assert snapshot.workflows[0].current_node == "run_verification"
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
    assert snapshot.capabilities[0].portability_export_status == "exported"
    assert snapshot.capabilities[0].portability_import_status == "imported"
    assert snapshot.capabilities[0].portability_validation_status == (
        "needs_adaptation"
    )
    assert snapshot.capabilities[0].portability_targets[0].target == ("codex:gpt-5.5")
    assert (
        snapshot.capabilities[0].portability_targets[0].portability_readiness_score
        == 0.42
    )
    assert snapshot.capabilities[0].next_action == (
        "run `omf verify capability repo_issue_triage`"
    )
    assert snapshot.learning_patches[0].capability_name == "repo_issue_triage"
    assert snapshot.learning_patches[0].decision == "accepted"
    assert snapshot.learning_patches[0].patch_kind == "harness"
    assert snapshot.comparisons[0].capability_name == "repo_issue_triage"
    assert snapshot.comparisons[0].eval_count == 1
    assert {action.kind for action in snapshot.console_actions} == {
        "review",
        "regression_case",
    }
    assert {event.kind for event in snapshot.events} >= {
        "approval_required",
        "learning_patch",
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
    assert len(snapshot.runtimes) == 6
    html = dashboard_html()
    assert "/api/snapshot" in html
    assert "/api/learning-patches" in html
    assert "/api/runtimes" in html
    assert "capability-rows" in html
    assert "learning-patch-rows" in html
    assert "workflow-rows" in html
    assert "runtime-cards" in html
    assert 'data-tab="runtimes"' in html


def test_dashboard_snapshot_lists_runtimes_without_installs(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)
    snapshot = build_dashboard_snapshot(paths)
    runtimes = {state.runtime for state in snapshot.runtimes}
    assert runtimes == {
        "codex",
        "claude_code",
        "hermes",
        "pi",
        "odysseus",
        "opencode",
    }
    for state in snapshot.runtimes:
        assert state.skill_installed is False
        assert state.mcp_installed is False


def _serve(paths: DashboardPaths) -> DashboardHTTPServer:
    server = create_dashboard_server(
        DashboardServeRequest(host="127.0.0.1", port=0, paths=paths),
    )
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    thread.start()
    return server


def _post(
    server: DashboardHTTPServer,
    path: str,
    payload: dict[str, object],
) -> dict[str, object]:
    host, port = cast("tuple[str, int]", server.server_address)
    request = urllib.request.Request(
        f"http://{host}:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
    decoded: dict[str, object] = json.loads(raw)
    return decoded


def test_install_skill_route_previews_then_applies(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)
    server = _serve(paths)
    try:
        preview = _post(
            server,
            "/api/install/skill",
            {"runtime": "claude_code", "dry_run": True},
        )
        assert preview["dry_run"] is True
        assert preview["installed"] is False
        assert Path(str(preview["skill_path"])).is_file() is False

        applied = _post(
            server,
            "/api/install/skill",
            {"runtime": "claude_code", "dry_run": False},
        )
        assert applied["installed"] is True
        assert Path(str(applied["skill_path"])).is_file() is True
    finally:
        server.shutdown()
        server.server_close()


def test_install_mcp_route_writes_config_on_apply(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)
    server = _serve(paths)
    try:
        applied = _post(
            server,
            "/api/install/mcp",
            {"client": "claude_code", "dry_run": False},
        )
        assert applied["installed"] is True
        assert Path(str(applied["config_path"])).is_file() is True
    finally:
        server.shutdown()
        server.server_close()


def test_capability_export_route_enforces_approval_gate(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)
    server = _serve(paths)
    try:
        # Unapproved export must be refused at the gate, never executed.
        refused = _post(
            server,
            "/api/capability/export",
            {"capability_name": "repo_issue_triage", "approve_export": False},
        )
        assert "error" in refused
        assert "approve-export" in str(refused["error"])

        # Approved request gets past the gate (then fails on the missing
        # capability), proving the flag is forwarded, not the gate bypassed.
        approved = _post(
            server,
            "/api/capability/export",
            {"capability_name": "repo_issue_triage", "approve_export": True},
        )
        assert "error" in approved
        assert "approve-export" not in str(approved["error"])
    finally:
        server.shutdown()
        server.server_close()


def test_capability_validate_route_rejects_run_command(tmp_path: Path) -> None:
    paths = make_dashboard_paths(tmp_path)
    server = _serve(paths)
    try:
        # The route model forbids run-command fields, so a client can never
        # make the server spawn a local process.
        rejected = _post(
            server,
            "/api/capability/validate",
            {
                "capability_name": "repo_issue_triage",
                "target": "claude_code",
                "run_command": "rm -rf /",
            },
        )
        assert "error" in rejected
    finally:
        server.shutdown()
        server.server_close()


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
        # Keep the runtime inventory hermetic: probe a tmp home, not the
        # developer's real ~/.claude, ~/.codex, etc.
        home=tmp_path / "home",
        project=tmp_path / "project",
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


def make_learning_patch() -> LearningPatchDecision:
    return LearningPatchDecision(
        id="20260602T010206Z-cafebabe",
        created_at=datetime(2026, 6, 2, 1, 2, 6, tzinfo=UTC),
        capability_name="repo_issue_triage",
        learning_id="20260602T010204Z-feedface",
        patch_kind="harness",
        patch="Always run pytest for this capability.",
        decision="accepted",
        reviewer="operator",
        pass_rate_delta=0.12,
    )


def write_portability_status(package_dir: Path) -> None:
    export_dir = package_dir / "exports" / "20260602T010207Z-export"
    export_dir.mkdir(parents=True)
    (export_dir / "export.yaml").write_text("id: export\n", encoding="utf-8")
    import_dir = package_dir / "imports" / "codex-gpt-5-5"
    import_dir.mkdir(parents=True)
    (import_dir / "target.overlay.yaml").write_text(
        "target:\n"
        "  runtime: codex\n"
        "  model: gpt-5.5\n"
        "status: needs_adaptation\n"
        "portability_readiness_score: 0.42\n"
        "eval_id: 20260602T010204Z-feedface\n",
        encoding="utf-8",
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
            nodes=("import_evidence", "run_verification"),
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
        current_node="run_verification",
        completed_nodes=("import_evidence", "promote_capability", "pack_context"),
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
                name="import_evidence",
                status="pass",
                message="captured",
            ),
            WorkflowNodeResult(
                name="promote_capability",
                status="pass",
                message="promoted",
            ),
            WorkflowNodeResult(
                name="pack_context",
                status="pass",
                message="packed",
            ),
        ),
        evidence_id=evidence_id,
        capability_name="repo_issue_triage",
        eval_id=eval_id,
    )
