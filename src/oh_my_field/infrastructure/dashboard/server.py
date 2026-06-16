import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from textwrap import dedent
from typing import Final, Literal, cast
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError

from oh_my_field.application.conformance import ConformanceError
from oh_my_field.application.install import install_mcp_config, install_omf_skill
from oh_my_field.application.install.mcp_workflow import McpInstallError
from oh_my_field.application.install.skill_workflow import SkillInstallError
from oh_my_field.application.portability import validate_capability_package
from oh_my_field.application.runtimes import (
    RuntimeInventoryRequest,
    run_runtime_inventory_workflow,
)
from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_CONTEXT_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_EVAL_SET_DIR,
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_EXPORTS_DIR,
    DEFAULT_LEARNING_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
    DEFAULT_REFLECTIONS_DIR,
    DEFAULT_REPLAYS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_WORKFLOWS_DIR,
)
from oh_my_field.domain.portability.models import (
    CapabilityValidationRequest,
    ExportTarget,
)
from oh_my_field.domain.skill.models import SkillInstallRequest, SkillInstallRuntime
from oh_my_field.export import ExportError, ExportRequest, run_export_workflow
from oh_my_field.health import health_entry_from_manifest
from oh_my_field.mcp.schemas import McpInstallClient, McpInstallRequest
from oh_my_field.models import (
    CapabilityManifest,
    CommandExecution,
    EvalResult,
    EvidenceRecord,
    HumanReviewAction,
    HumanReviewRecord,
    LearningPatchDecision,
    ReplayRecord,
    ReviewTargetType,
    StrictModel,
    WorkflowNodeResult,
    WorkflowNodeStatus,
    WorkflowRunRecord,
)
from oh_my_field.orchestrate import ORCHESTRATOR_NODES
from oh_my_field.review import ReviewError, ReviewRequest, run_review_workflow
from oh_my_field.storage import (
    StorageError,
    list_eval_results,
    list_eval_sets,
    list_learning_patch_decisions,
    list_manifests,
    read_portability_health,
)

DEFAULT_DASHBOARD_PORT: Final = 8765
APPROVAL_TIMEOUT_SECONDS: Final = 1_800
MAX_EVENTS: Final = 50

type DashboardEventSeverity = Literal["info", "warning", "critical"]
type DashboardNodeStatus = WorkflowNodeStatus | Literal["running"]


class DashboardError(Exception):
    pass


class DashboardPaths(StrictModel):
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR
    replay_dir: Path = DEFAULT_REPLAYS_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR
    workflow_dir: Path = DEFAULT_WORKFLOWS_DIR
    review_dir: Path = DEFAULT_REVIEW_DIR
    eval_set_dir: Path = DEFAULT_EVAL_SET_DIR
    learning_patch_dir: Path = DEFAULT_LEARNING_PATCH_DIR
    project: Path = Path()
    home: Path | None = None


class DashboardServeRequest(StrictModel):
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=DEFAULT_DASHBOARD_PORT, ge=0, le=65_535)
    paths: DashboardPaths = Field(default_factory=DashboardPaths)


class DashboardArtifactIds(StrictModel):
    evidence_id: str | None = None
    replay_id: str | None = None
    eval_id: str | None = None
    context_id: str | None = None
    learning_id: str | None = None


class DashboardNode(StrictModel):
    name: str
    status: DashboardNodeStatus
    message: str | None = None
    path: str | None = None


class DashboardWorkflowSummary(StrictModel):
    id: str
    goal: str
    status: str
    current_node: str | None
    capability_name: str | None
    created_at: datetime
    updated_at: datetime
    elapsed_ms: int
    runtime: str
    model: str | None
    progress_percent: int
    completed_node_count: int
    total_node_count: int
    failed_node: str | None
    failure_reason: str | None
    nodes: tuple[DashboardNode, ...]
    artifacts: DashboardArtifactIds
    command_count: int
    harness_command_count: int
    pending_approval_count: int
    cost_usd: float
    latency_ms: int
    replay_command: str | None


class DashboardPortabilityTarget(StrictModel):
    target: str
    validation_status: str
    portability_readiness_score: float | None
    eval_recorded: bool


class DashboardCapabilitySummary(StrictModel):
    name: str
    version: str
    description: str
    status: str
    runtime: str
    model: str | None
    tools: tuple[str, ...]
    network_policy: str
    required_checks: tuple[str, ...]
    evaluation_results: tuple[str, ...]
    source_evidence_count: int
    eval_count: int
    pass_rate: float
    patch_count: int
    promotion_success_runs: int
    promotion_harness_pass_rate: float
    promotion_eval_pass_rate: float
    promotion_criteria_met: bool
    integrity_status: str
    next_action: str
    portability_export_status: str
    portability_import_status: str
    portability_validation_status: str
    portability_export_count: int
    portability_import_count: int
    portability_target_validation_count: int
    portability_targets: tuple["DashboardPortabilityTarget", ...]
    manifest_path: str


class DashboardEvalSummary(StrictModel):
    id: str
    capability_name: str
    replay_id: str | None
    status: str
    created_at: datetime
    check_count: int
    failure_count: int
    command_count: int
    latency_ms: int


class DashboardReplaySummary(StrictModel):
    id: str
    capability_name: str
    source_evidence_id: str
    created_at: datetime
    runtime: str
    model: str | None
    harness_status: str
    command_count: int
    latency_ms: int


class DashboardReviewSummary(StrictModel):
    id: str
    target_type: str
    target_id: str
    action: str
    status: str
    reviewer: str | None
    created_at: datetime
    notes: tuple[str, ...]
    revision_request: str | None


class DashboardLearningPatchSummary(StrictModel):
    id: str
    capability_name: str
    learning_id: str
    patch_kind: str
    decision: str
    reviewer: str | None
    created_at: datetime
    notes: tuple[str, ...]
    pass_rate_delta: float | None
    manifest_path: str | None


class DashboardApprovalRequest(StrictModel):
    id: str
    target_type: ReviewTargetType
    target_id: str
    source: str
    created_at: datetime
    age_seconds: int
    timed_out: bool
    command: str
    risk_categories: tuple[str, ...]
    reason: str


class DashboardEvent(StrictModel):
    id: str
    created_at: datetime
    severity: DashboardEventSeverity
    kind: str
    title: str
    message: str
    workflow_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    node: str | None = None


class DashboardMetrics(StrictModel):
    workflow_count: int
    running_count: int
    completed_count: int
    failed_count: int
    pending_review_count: int
    capability_count: int
    harness_pass_rate: float
    user_intervention_count: int
    pending_approval_count: int
    regression_case_count: int
    learning_patch_count: int


class DashboardCapabilityComparison(StrictModel):
    capability_name: str
    run_count: int
    eval_count: int
    pass_count: int
    fail_count: int
    pass_rate: float
    runtime_profiles: tuple[str, ...]
    average_latency_ms: int


class DashboardConsoleAction(StrictModel):
    kind: str
    title: str
    command: str
    target_type: str | None = None
    target_id: str | None = None


class DashboardRuntimeSummary(StrictModel):
    runtime: str
    presence: str
    presence_detail: str
    skill_installed: bool
    mcp_installed: bool
    conformance_status: str
    overall_status: str
    next_action: str
    skill_path: str
    mcp_config_path: str


class DashboardSnapshot(StrictModel):
    generated_at: datetime
    metrics: DashboardMetrics
    workflows: tuple[DashboardWorkflowSummary, ...]
    capabilities: tuple[DashboardCapabilitySummary, ...]
    runtimes: tuple[DashboardRuntimeSummary, ...]
    replays: tuple[DashboardReplaySummary, ...]
    evals: tuple[DashboardEvalSummary, ...]
    reviews: tuple[DashboardReviewSummary, ...]
    learning_patches: tuple[DashboardLearningPatchSummary, ...]
    approvals: tuple[DashboardApprovalRequest, ...]
    events: tuple[DashboardEvent, ...]
    comparisons: tuple[DashboardCapabilityComparison, ...]
    console_actions: tuple[DashboardConsoleAction, ...]


class DashboardReviewRequest(StrictModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)
    action: HumanReviewAction
    reviewer: str | None = None
    notes: tuple[str, ...] = ()
    revision_request: str | None = None
    added_context: tuple[str, ...] = ()
    changed_goal: str | None = None
    changed_constraint: str | None = None
    regression_case: str | None = None


class DashboardSkillInstallRequest(StrictModel):
    # dry_run defaults True: the UI previews the plan, then re-sends with
    # dry_run=false on an explicit "Apply". The server never silently writes.
    runtime: SkillInstallRuntime
    dry_run: bool = True
    overwrite: bool = False


class DashboardMcpInstallRequest(StrictModel):
    client: McpInstallClient
    dry_run: bool = True
    overwrite: bool = False


class DashboardCapabilityExportRequest(StrictModel):
    # approve_export defaults False; the export workflow raises until the UI
    # re-sends with approve_export=true. The server only forwards the flag.
    capability_name: str = Field(min_length=1)
    approve_export: bool = False


class DashboardCapabilityValidateRequest(StrictModel):
    # Record-only validation: no run-command/approval is accepted over HTTP, so
    # a client can never make the server spawn a local process. A real
    # `validated` status still goes through the risk-gated `omf capability
    # validate --run-command` CLI path (see the summary's next_commands).
    capability_name: str = Field(min_length=1)
    target: ExportTarget
    model: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalCommandContext:
    target_type: ReviewTargetType
    target_id: str
    source: str
    created_at: datetime
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class DashboardMetricCounts:
    user_intervention_count: int
    regression_case_count: int
    learning_patch_count: int


def build_dashboard_snapshot(paths: DashboardPaths) -> DashboardSnapshot:
    generated_at = datetime.now(UTC)
    evidence = _list_json_models(paths.evidence_dir, EvidenceRecord)
    replays = _list_json_models(paths.replay_dir, ReplayRecord)
    evals = list_eval_results(paths.eval_dir)
    eval_sets = list_eval_sets(paths.eval_set_dir)
    learning_patch_decisions = list_learning_patch_decisions(paths.learning_patch_dir)
    reviews = _list_json_models(paths.review_dir, HumanReviewRecord)
    workflows = _list_json_models(paths.workflow_dir, WorkflowRunRecord)
    approvals = _approval_requests(evidence, replays, evals, reviews, generated_at)
    workflow_summaries = _workflow_summaries(workflows, evidence, evals, approvals)
    capability_summaries = _capability_summaries(paths, evals)
    replay_summaries = tuple(_replay_summary(replay) for replay in replays)
    eval_summaries = tuple(_eval_summary(result) for result in evals)
    review_summaries = tuple(_review_summary(review) for review in reviews)
    learning_patch_summaries = tuple(
        _learning_patch_summary(decision) for decision in learning_patch_decisions
    )
    runtime_summaries = _runtime_summaries(paths)
    comparisons = _capability_comparisons(workflow_summaries, eval_summaries)
    events = _events(
        workflow_summaries,
        approvals,
        review_summaries,
        learning_patch_summaries,
    )
    return DashboardSnapshot(
        generated_at=generated_at,
        metrics=_metrics(
            workflow_summaries,
            capability_summaries,
            eval_summaries,
            approvals,
            DashboardMetricCounts(
                user_intervention_count=_user_intervention_count(
                    evidence,
                    review_summaries,
                ),
                regression_case_count=sum(
                    len(eval_set.cases) for eval_set in eval_sets
                ),
                learning_patch_count=len(learning_patch_decisions),
            ),
        ),
        workflows=workflow_summaries,
        capabilities=capability_summaries,
        runtimes=runtime_summaries,
        replays=replay_summaries,
        evals=eval_summaries,
        reviews=review_summaries,
        learning_patches=learning_patch_summaries,
        approvals=approvals,
        events=events,
        comparisons=comparisons,
        console_actions=_console_actions(approvals, eval_summaries),
    )


def record_dashboard_review(
    request: DashboardReviewRequest,
    paths: DashboardPaths,
) -> str:
    summary = run_review_workflow(
        ReviewRequest(
            target_type=request.target_type,
            target_id=request.target_id,
            action=request.action,
            reviewer=request.reviewer,
            notes=request.notes,
            revision_request=request.revision_request,
            added_context=request.added_context,
            changed_goal=request.changed_goal,
            changed_constraint=request.changed_constraint,
            regression_case=request.regression_case,
            review_dir=paths.review_dir,
        ),
    )
    return summary.model_dump_json()


def create_dashboard_server(request: DashboardServeRequest) -> "DashboardHTTPServer":
    return DashboardHTTPServer(
        (request.host, request.port),
        DashboardRequestHandler,
        request.paths,
    )


def dashboard_html() -> str:
    return dedent(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>oh-my-field</title>
          <style>
            :root {
              color-scheme: light;
              --ink: #18202a;
              --muted: #657384;
              --line: #d8dee8;
              --panel: #ffffff;
              --band: #f5f7fb;
              --accent: #0f766e;
              --warn: #b45309;
              --fail: #b91c1c;
              --pass: #15803d;
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              color: var(--ink);
              background: var(--band);
              font-family: ui-sans-serif, system-ui, -apple-system,
                BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            header {
              display: flex;
              align-items: center;
              gap: 24px;
              min-height: 56px;
              padding: 0 20px;
              background: #ffffff;
              border-bottom: 1px solid var(--line);
            }
            .brand { display: flex; align-items: baseline; gap: 10px; }
            header h1 { margin: 0; font-size: 17px; font-weight: 700; }
            #updated { color: var(--muted); font-size: 12px; }
            .tabs { display: flex; gap: 4px; margin-left: auto; }
            .tab {
              padding: 8px 14px;
              border: 1px solid transparent;
              border-radius: 6px;
              background: transparent;
              color: var(--muted);
              font-size: 14px;
              cursor: pointer;
            }
            .tab:hover { background: #eef2f7; }
            .tab.active {
              color: var(--ink);
              font-weight: 600;
              background: #e8eef6;
            }
            main { padding: 16px; }
            .panel[hidden] { display: none; }
            .grid2 {
              display: grid;
              grid-template-columns: minmax(360px, 1.1fr) minmax(320px, 0.9fr);
              gap: 16px;
            }
            section {
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 6px;
              overflow: hidden;
              margin-bottom: 16px;
            }
            section h2 {
              margin: 0;
              padding: 12px 14px;
              font-size: 14px;
              border-bottom: 1px solid var(--line);
            }
            .content { padding: 12px 14px; }
            .metrics {
              display: grid;
              grid-template-columns: repeat(4, minmax(120px, 1fr));
              gap: 10px;
            }
            .metric {
              padding: 10px;
              border: 1px solid var(--line);
              border-radius: 6px;
              background: #fbfcfe;
            }
            .metric span { color: var(--muted); font-size: 12px; }
            .metric b { display: block; margin-top: 5px; font-size: 18px; }
            table { width: 100%; border-collapse: collapse; font-size: 13px; }
            th, td {
              padding: 9px 10px;
              border-bottom: 1px solid var(--line);
              text-align: left;
              vertical-align: top;
            }
            th { color: var(--muted); font-weight: 600; }
            tr[data-run] { cursor: pointer; }
            tr[data-run]:hover { background: #f3f7fb; }
            .tag {
              display: inline-block;
              padding: 2px 6px;
              border-radius: 6px;
              background: #e8eef6;
              font-size: 12px;
            }
            .pass { color: var(--pass); }
            .fail { color: var(--fail); }
            .warn { color: var(--warn); }
            .cards {
              display: grid;
              grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
              gap: 12px;
            }
            .card {
              border: 1px solid var(--line);
              border-radius: 6px;
              background: #fbfcfe;
              padding: 12px;
            }
            .card h3 {
              margin: 0 0 8px;
              font-size: 14px;
              display: flex;
              justify-content: space-between;
              align-items: center;
            }
            .badge {
              font-size: 11px;
              padding: 2px 8px;
              border-radius: 999px;
              border: 1px solid var(--line);
            }
            .badge.ready { color: var(--pass); border-color: #86efac; }
            .badge.partial { color: var(--warn); border-color: #fcd34d; }
            .badge.absent { color: var(--muted); }
            .checks { font-size: 13px; margin: 6px 0; }
            .next { color: var(--muted); font-size: 12px; margin: 6px 0; }
            .graph {
              display: grid;
              grid-template-columns: repeat(6, minmax(86px, 1fr));
              gap: 8px;
            }
            .node {
              min-height: 70px;
              padding: 8px;
              border: 1px solid var(--line);
              border-radius: 6px;
              background: #fbfcfe;
              overflow-wrap: anywhere;
            }
            .node.pass { border-color: #86efac; background: #f0fdf4; }
            .node.fail { border-color: #fecaca; background: #fff1f2; }
            .node.running { border-color: #5eead4; background: #ecfeff; }
            .progress {
              height: 8px;
              margin-top: 8px;
              background: #e5e9f0;
              border-radius: 999px;
              overflow: hidden;
            }
            .progress span {
              display: block;
              height: 100%;
              background: var(--accent);
            }
            .event { padding: 9px 0; border-bottom: 1px solid var(--line); }
            .event:last-child { border-bottom: 0; }
            .controls {
              display: flex;
              gap: 10px;
              flex-wrap: wrap;
              align-items: center;
              margin-bottom: 10px;
            }
            button, select, input {
              min-height: 32px;
              border: 1px solid var(--line);
              border-radius: 6px;
              background: #ffffff;
              color: var(--ink);
            }
            button { padding: 0 10px; cursor: pointer; }
            .act { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
            pre {
              max-height: 280px;
              overflow: auto;
              margin: 8px 0 0;
              padding: 12px;
              background: #111827;
              color: #e5e7eb;
              border-radius: 6px;
              font-size: 12px;
              white-space: pre-wrap;
              overflow-wrap: anywhere;
            }
            footer { padding: 12px 16px; color: var(--muted); font-size: 12px; }
            @media (max-width: 900px) {
              .grid2 { grid-template-columns: 1fr; }
              .metrics { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
              .graph { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
              .tabs { flex-wrap: wrap; }
            }
          </style>
        </head>
        <body>
          <header>
            <div class="brand">
              <h1>oh-my-field</h1>
              <span id="updated">loading</span>
            </div>
            <nav class="tabs" id="tabs">
              <button class="tab active" data-tab="overview">Overview</button>
              <button class="tab" data-tab="runtimes">Runtimes</button>
              <button class="tab" data-tab="capabilities">Capabilities</button>
              <button class="tab" data-tab="workflows">Workflows</button>
            </nav>
          </header>
          <main>
            <div class="panel" data-panel="overview">
              <section>
                <h2>Metrics</h2>
                <div class="content metrics" id="metrics"></div>
              </section>
              <section>
                <h2>Needs attention</h2>
                <div class="content" id="attention"></div>
              </section>
            </div>

            <div class="panel" data-panel="runtimes" hidden>
              <section>
                <h2>Agent runtimes &middot; skill &amp; MCP status</h2>
                <div class="content cards" id="runtime-cards"></div>
              </section>
            </div>

            <div class="panel" data-panel="capabilities" hidden>
              <section>
                <h2>Capability portability</h2>
                <div class="content">
                  <table>
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Health</th>
                        <th>Export / Import / Validate</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody id="capability-rows"></tbody>
                  </table>
                  <pre id="cap-output" hidden></pre>
                </div>
              </section>
            </div>

            <div class="panel" data-panel="workflows" hidden>
              <div class="grid2">
                <section>
                  <h2>Workflow runs</h2>
                  <div class="content">
                    <div class="controls">
                      <select id="status-filter">
                        <option value="">All status</option>
                        <option value="running">running</option>
                        <option value="completed">completed</option>
                        <option value="failed">failed</option>
                        <option value="pending_review">pending review</option>
                      </select>
                      <input id="search" placeholder="filter">
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>Run</th>
                          <th>Status</th>
                          <th>Capability</th>
                          <th>Progress</th>
                        </tr>
                      </thead>
                      <tbody id="workflow-rows"></tbody>
                    </table>
                  </div>
                </section>
                <section>
                  <h2>Approvals</h2>
                  <div class="content" id="approval-list"></div>
                </section>
              </div>
              <section>
                <h2>Workflow graph</h2>
                <div class="content">
                  <div id="selected-run"></div>
                  <div class="graph" id="graph-nodes"></div>
                </div>
              </section>
              <section>
                <h2>Events</h2>
                <div class="content">
                  <div class="controls">
                    <label><input type="checkbox" data-severity="info" checked>
                      info</label>
                    <label><input type="checkbox" data-severity="warning"
                      checked> warning</label>
                    <label><input type="checkbox" data-severity="critical"
                      checked> critical</label>
                  </div>
                  <div id="event-list"></div>
                </div>
              </section>
              <section>
                <h2>Learning patches</h2>
                <div class="content">
                  <table>
                    <thead>
                      <tr>
                        <th>Patch</th>
                        <th>Decision</th>
                        <th>Reviewer</th>
                        <th>Eval delta</th>
                      </tr>
                    </thead>
                    <tbody id="learning-patch-rows"></tbody>
                  </table>
                </div>
              </section>
              <section>
                <h2>Execution history</h2>
                <div class="content">
                  <table>
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Runs</th>
                        <th>Evals</th>
                        <th>Pass rate</th>
                        <th>Runtime profiles</th>
                      </tr>
                    </thead>
                    <tbody id="comparison-rows"></tbody>
                  </table>
                </div>
              </section>
            </div>
          </main>
          <footer>
            Local API: /api/snapshot /api/runtimes /api/capabilities
            /api/learning-patches
          </footer>
          <script>
            let snapshot = null;
            let selectedRunId = null;
            let activeTab = "overview";

            const byId = (id) => document.getElementById(id);
            const pct = (value) => `${Math.round(value)}%`;
            const shortId = (value) => value ? value.slice(0, 18) : "";
            const mark = (ok) => ok
              ? '<span class="pass">&#10003;</span>'
              : '<span class="fail">&#10007;</span>';
            const esc = (value) => String(value == null ? "" : value)
              .replace(/&/g, "&amp;").replace(/</g, "&lt;")
              .replace(/>/g, "&gt;").replace(/"/g, "&quot;");

            async function postJson(url, payload) {
              const response = await fetch(url, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
              });
              return response.json();
            }

            async function refresh() {
              const response = await fetch("/api/snapshot");
              snapshot = await response.json();
              if (!selectedRunId && snapshot.workflows.length > 0) {
                selectedRunId = snapshot.workflows[0].id;
              }
              render();
            }

            function render() {
              if (!snapshot) return;
              byId("updated").textContent = snapshot.generated_at;
              renderMetrics();
              renderAttention();
              renderRuntimes();
              renderWorkflows();
              renderGraph();
              renderApprovals();
              renderCapabilities();
              renderLearningPatches();
              renderEvents();
              renderComparisons();
            }

            function setTab(name) {
              activeTab = name;
              document.querySelectorAll(".tab").forEach((tab) => {
                tab.classList.toggle("active", tab.dataset.tab === name);
              });
              document.querySelectorAll(".panel").forEach((panel) => {
                panel.hidden = panel.dataset.panel !== name;
              });
            }

            function renderMetrics() {
              const m = snapshot.metrics;
              const ready = (snapshot.runtimes || [])
                .filter((r) => r.overall_status === "ready").length;
              const items = [
                ["Workflows", m.workflow_count],
                ["Running", m.running_count],
                ["Pending approvals", m.pending_approval_count],
                ["Harness pass", pct(m.harness_pass_rate)],
                ["Capabilities", m.capability_count],
                ["Ready runtimes", ready],
                ["Regression cases", m.regression_case_count],
                ["Learning patches", m.learning_patch_count]
              ];
              byId("metrics").innerHTML = items.map((item) =>
                `<div class="metric"><span>${item[0]}</span>` +
                `<b>${item[1]}</b></div>`
              ).join("");
            }

            function renderAttention() {
              const failed = snapshot.workflows
                .filter((run) => run.status === "failed");
              const approvals = snapshot.approvals || [];
              const parts = [];
              approvals.forEach((item) => parts.push(
                `<div class="event"><strong class="warn">Approval` +
                ` required</strong><div>${esc(item.reason)}</div>` +
                `<code>${esc(item.command)}</code></div>`
              ));
              failed.forEach((run) => parts.push(
                `<div class="event"><strong class="fail">Workflow` +
                ` failed</strong><div>${esc(run.goal)}</div>` +
                `<small>${esc(run.failure_reason || "")}</small></div>`
              ));
              byId("attention").innerHTML = parts.length
                ? parts.join("")
                : "<p>Nothing needs attention.</p>";
            }

            function renderRuntimes() {
              const rows = snapshot.runtimes || [];
              if (rows.length === 0) {
                byId("runtime-cards").innerHTML =
                  "<p>No runtime information available.</p>";
                return;
              }
              byId("runtime-cards").innerHTML = rows.map((r) =>
                `<div class="card">
                  <h3>${esc(r.runtime)}
                    <span class="badge ${r.overall_status}">` +
                    `${esc(r.overall_status)}</span></h3>
                  <div class="checks">presence: ${esc(r.presence)}</div>
                  <div class="checks">skill ${mark(r.skill_installed)}
                    &nbsp; MCP ${mark(r.mcp_installed)}</div>
                  <div class="next">${esc(r.next_action)}</div>
                  <div class="act">
                    <button onclick="runtimeSkill('${esc(r.runtime)}', false)">
                      Preview skill</button>
                    <button onclick="runtimeSkill('${esc(r.runtime)}', true)">
                      Install skill</button>
                    <button onclick="runtimeMcp('${esc(r.runtime)}', false)">
                      Preview MCP</button>
                    <button onclick="runtimeMcp('${esc(r.runtime)}', true)">
                      Install MCP</button>
                  </div>
                  <pre class="card-out" hidden></pre>
                </div>`
              ).join("");
            }

            function cardOut(runtime) {
              const cards = document.querySelectorAll("#runtime-cards .card");
              for (const card of cards) {
                if (card.querySelector("h3").textContent.trim()
                    .startsWith(runtime)) {
                  return card.querySelector(".card-out");
                }
              }
              return null;
            }

            function showCardOut(runtime, data) {
              const out = cardOut(runtime);
              if (!out) return;
              out.hidden = false;
              out.textContent = JSON.stringify(data, null, 2);
            }

            async function runtimeSkill(runtime, apply) {
              if (apply && !window.confirm(
                  `Install the OMF skill for ${runtime}?`)) return;
              const data = await postJson("/api/install/skill", {
                runtime: runtime, dry_run: !apply
              });
              showCardOut(runtime, data);
              if (apply) refresh();
            }

            async function runtimeMcp(runtime, apply) {
              if (apply && !window.confirm(
                  `Install the OMF MCP config for ${runtime}?`)) return;
              const data = await postJson("/api/install/mcp", {
                client: runtime, dry_run: !apply
              });
              showCardOut(runtime, data);
              if (apply) refresh();
            }

            function showCapOutput(data) {
              const out = byId("cap-output");
              out.hidden = false;
              out.textContent = JSON.stringify(data, null, 2);
            }

            async function exportCapability(name) {
              let data = await postJson("/api/capability/export", {
                capability_name: name, approve_export: false
              });
              if (data.error) {
                if (window.confirm(`${data.error}\\n\\nApprove and export?`)) {
                  data = await postJson("/api/capability/export", {
                    capability_name: name, approve_export: true
                  });
                }
              }
              showCapOutput(data);
              refresh();
            }

            async function validateCapability(name, target) {
              const chosen = window.prompt("Validate against target", target);
              if (!chosen) return;
              const data = await postJson("/api/capability/validate", {
                capability_name: name, target: chosen
              });
              showCapOutput(data);
              refresh();
            }

            function renderWorkflows() {
              const status = byId("status-filter").value;
              const query = byId("search").value.toLowerCase();
              const rows = snapshot.workflows.filter((run) => {
                const okStatus = !status || run.status === status;
                const hay =
                  `${run.id} ${run.goal} ${run.capability_name || ""}`;
                return okStatus && hay.toLowerCase().includes(query);
              });
              byId("workflow-rows").innerHTML = rows.map((run) =>
                `<tr data-run="${run.id}" onclick="selectRun('${run.id}')">
                  <td>${shortId(run.id)}<br>${esc(run.goal)}</td>
                  <td><span class="tag">${esc(run.status)}</span></td>
                  <td>${esc(run.capability_name || "")}<br>` +
                  `${esc(run.runtime)}</td>
                  <td>${pct(run.progress_percent)}
                    <div class="progress">
                      <span style="width:${run.progress_percent}%"></span>
                    </div>
                  </td>
                </tr>`
              ).join("");
            }

            function renderGraph() {
              const run = selectedRun();
              if (!run) {
                byId("selected-run").textContent = "No workflow selected";
                byId("graph-nodes").innerHTML = "";
                return;
              }
              byId("selected-run").textContent =
                `${shortId(run.id)} ${run.status} ` +
                `${pct(run.progress_percent)}`;
              byId("graph-nodes").innerHTML = run.nodes.map((node) =>
                `<div class="node ${node.status}">
                  <strong>${esc(node.name)}</strong><br>
                  <span>${esc(node.status)}</span><br>
                  <small>${esc(node.message || "")}</small>
                </div>`
              ).join("");
            }

            function renderApprovals() {
              const approvals = snapshot.approvals;
              if (approvals.length === 0) {
                byId("approval-list").innerHTML = "<p>No pending approvals.</p>";
                return;
              }
              byId("approval-list").innerHTML = approvals.map((item) =>
                `<div class="event">
                  <strong>${esc(item.target_type)} ` +
                  `${shortId(item.target_id)}</strong>
                  <div>${esc(item.reason)}</div>
                  <code>${esc(item.command)}</code><br>
                  <button onclick="review('${item.target_type}',
                    '${item.target_id}', 'approve')">Approve</button>
                  <button onclick="review('${item.target_type}',
                    '${item.target_id}', 'reject')">Reject</button>
                  <button onclick="revise('${item.target_type}',
                    '${item.target_id}')">Revise</button>
                </div>`
              ).join("");
            }

            function renderCapabilities() {
              const rows = snapshot.capabilities || [];
              if (rows.length === 0) {
                byId("capability-rows").innerHTML =
                  "<tr><td colspan='4'>No capabilities.</td></tr>";
                return;
              }
              byId("capability-rows").innerHTML = rows.map((item) => {
                const targets = (item.portability_targets || []).map((t) =>
                  `${esc(t.target)}: ${esc(t.validation_status)}`
                ).join("<br>");
                const port =
                  `${esc(item.portability_export_status)} / ` +
                  `${esc(item.portability_import_status)} / ` +
                  `${esc(item.portability_validation_status)}`;
                const rt = esc(item.runtime);
                return `<tr>
                  <td>${esc(item.name)}<br>` +
                  `<span class="tag">${esc(item.status)}</span></td>
                  <td>${esc(item.integrity_status)}<br>` +
                  `${pct(item.pass_rate)}</td>
                  <td>${port}<br><small>${targets}</small></td>
                  <td><button onclick="exportCapability(` +
                  `'${esc(item.name)}')">Export</button>
                    <button onclick="validateCapability(` +
                    `'${esc(item.name)}', '${rt}')">Validate</button></td>
                </tr>`;
              }).join("");
            }

            function renderLearningPatches() {
              const rows = snapshot.learning_patches || [];
              if (rows.length === 0) {
                byId("learning-patch-rows").innerHTML =
                  "<tr><td colspan='4'>No learning patches.</td></tr>";
                return;
              }
              byId("learning-patch-rows").innerHTML = rows.map((item) =>
                `<tr>
                  <td>${shortId(item.id)}<br>${esc(item.capability_name)}
                    <br><span class="tag">${esc(item.patch_kind)}</span></td>
                  <td>${esc(item.decision)}</td>
                  <td>${esc(item.reviewer || "")}</td>
                  <td>${item.pass_rate_delta ?? ""}</td>
                </tr>`
              ).join("");
            }

            function renderEvents() {
              const enabled = {};
              document.querySelectorAll("[data-severity]").forEach((input) => {
                enabled[input.dataset.severity] = input.checked;
              });
              byId("event-list").innerHTML = snapshot.events
                .filter((event) => enabled[event.severity])
                .map((event) =>
                  `<div class="event ${event.severity}">
                    <strong>${esc(event.title)}</strong>
                    <div>${esc(event.message)}</div>
                    <small>${esc(event.created_at)}</small>
                  </div>`
                ).join("");
            }

            function renderComparisons() {
              byId("comparison-rows").innerHTML =
                snapshot.comparisons.map((item) =>
                  `<tr>
                    <td>${esc(item.capability_name)}</td>
                    <td>${item.run_count}</td>
                    <td>${item.eval_count}</td>
                    <td>${pct(item.pass_rate)}</td>
                    <td>${esc(item.runtime_profiles.join(", "))}</td>
                  </tr>`
                ).join("");
            }

            function selectedRun() {
              return snapshot.workflows.find((r) => r.id === selectedRunId);
            }

            function selectRun(runId) {
              selectedRunId = runId;
              renderGraph();
            }

            async function review(targetType, targetId, action) {
              await postJson("/api/reviews", {
                target_type: targetType,
                target_id: targetId,
                action: action,
                notes: [`dashboard ${action}`]
              });
              await refresh();
            }

            async function revise(targetType, targetId) {
              const revision = window.prompt("Revision request");
              if (!revision) return;
              await postJson("/api/reviews", {
                target_type: targetType,
                target_id: targetId,
                action: "revise",
                revision_request: revision
              });
              await refresh();
            }

            document.querySelectorAll(".tab").forEach((tab) =>
              tab.addEventListener("click", () => setTab(tab.dataset.tab))
            );
            byId("status-filter").addEventListener("change", renderWorkflows);
            byId("search").addEventListener("input", renderWorkflows);
            document.querySelectorAll("[data-severity]").forEach((input) =>
              input.addEventListener("change", renderEvents)
            );
            refresh();
            setInterval(refresh, 2000);
          </script>
        </body>
        </html>
        """,
    ).strip()


class DashboardHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        paths: DashboardPaths,
    ) -> None:
        """Create a local dashboard server bound to artifact storage paths."""
        super().__init__(server_address, handler_class)
        self.paths = paths


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "oh-my-field-dashboard/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_text(dashboard_html(), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/snapshot":
            self._send_snapshot()
            return
        route = _snapshot_route(parsed.path, build_dashboard_snapshot(self._paths()))
        if route is not None:
            self._send_json(route)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "route not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        handlers: dict[str, Callable[[bytes], None]] = {
            "/api/reviews": self._post_review,
            "/api/install/skill": self._post_install_skill,
            "/api/install/mcp": self._post_install_mcp,
            "/api/capability/export": self._post_capability_export,
            "/api/capability/validate": self._post_capability_validate,
        }
        handler = handlers.get(parsed.path)
        if handler is None:
            self._send_error(HTTPStatus.NOT_FOUND, "route not found")
            return
        body = self._read_body()
        if body is None:
            return
        handler(body)

    def _read_body(self) -> bytes | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid content length")
            return None
        return self.rfile.read(content_length)

    def _post_review(self, body: bytes) -> None:
        try:
            request = DashboardReviewRequest.model_validate_json(body)
            response = record_dashboard_review(request, self._paths())
        except (ReviewError, StorageError, ValidationError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_text(response, "application/json; charset=utf-8")

    def _post_install_skill(self, body: bytes) -> None:
        paths = self._paths()
        try:
            request = DashboardSkillInstallRequest.model_validate_json(body)
            summary = install_omf_skill(
                SkillInstallRequest(
                    runtime=request.runtime,
                    project=paths.project,
                    home=paths.home,
                    dry_run=request.dry_run,
                    overwrite=request.overwrite,
                ),
            )
        except (SkillInstallError, StorageError, ValidationError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_text(summary.model_dump_json(), "application/json; charset=utf-8")

    def _post_install_mcp(self, body: bytes) -> None:
        paths = self._paths()
        try:
            request = DashboardMcpInstallRequest.model_validate_json(body)
            summary = install_mcp_config(
                McpInstallRequest(
                    client=request.client,
                    project=paths.project,
                    home=paths.home,
                    dry_run=request.dry_run,
                    overwrite=request.overwrite,
                ),
            )
        except (McpInstallError, StorageError, ValidationError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_text(summary.model_dump_json(), "application/json; charset=utf-8")

    def _post_capability_export(self, body: bytes) -> None:
        paths = self._paths()
        try:
            request = DashboardCapabilityExportRequest.model_validate_json(body)
            summary = run_export_workflow(
                ExportRequest(
                    capability_name=request.capability_name,
                    approve_export=request.approve_export,
                    capabilities_dir=paths.capabilities_dir,
                    evidence_dir=paths.evidence_dir,
                    eval_dir=paths.eval_dir,
                    context_dir=DEFAULT_CONTEXT_DIR,
                    learning_dir=DEFAULT_LEARNING_DIR,
                    reflection_dir=DEFAULT_REFLECTIONS_DIR,
                    export_dir=DEFAULT_EXPORTS_DIR,
                ),
            )
        except (ExportError, StorageError, ValidationError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_text(summary.model_dump_json(), "application/json; charset=utf-8")

    def _post_capability_validate(self, body: bytes) -> None:
        paths = self._paths()
        try:
            request = DashboardCapabilityValidateRequest.model_validate_json(body)
            summary = validate_capability_package(
                CapabilityValidationRequest(
                    capability_name=request.capability_name,
                    capabilities_dir=paths.capabilities_dir,
                    eval_dir=paths.eval_dir,
                    evidence_dir=paths.evidence_dir,
                    target=request.target,
                    model=request.model,
                ),
            )
        except (StorageError, ValidationError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_text(summary.model_dump_json(), "application/json; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args

    def _paths(self) -> DashboardPaths:
        return _dashboard_server(self.server).paths

    def _send_snapshot(self) -> None:
        self._send_text(
            build_dashboard_snapshot(self._paths()).model_dump_json(),
            "application/json; charset=utf-8",
        )

    def _send_json(self, models: Iterable[BaseModel]) -> None:
        payload = [json.loads(model.model_dump_json()) for model in models]
        self._send_text(
            json.dumps(payload, separators=(",", ":")),
            "application/json; charset=utf-8",
        )

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_text(
            json.dumps({"error": message}, separators=(",", ":")),
            "application/json; charset=utf-8",
            status,
        )

    def _send_text(
        self,
        body: str,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        payload = body.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def _dashboard_server(server: object) -> DashboardHTTPServer:
    return cast("DashboardHTTPServer", server)


def _snapshot_route(
    path: str,
    snapshot: DashboardSnapshot,
) -> tuple[BaseModel, ...] | None:
    routes: dict[str, tuple[BaseModel, ...]] = {
        "/api/workflows": snapshot.workflows,
        "/api/events": snapshot.events,
        "/api/approvals": snapshot.approvals,
        "/api/capabilities": snapshot.capabilities,
        "/api/runtimes": snapshot.runtimes,
        "/api/learning-patches": snapshot.learning_patches,
        "/api/actions": snapshot.console_actions,
    }
    return routes.get(path)


def _list_json_models[ModelT: BaseModel](
    artifact_dir: Path,
    model: type[ModelT],
) -> tuple[ModelT, ...]:
    if not artifact_dir.exists():
        return ()
    return tuple(
        model.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(artifact_dir.glob("*.json"))
    )


def _workflow_summaries(
    records: tuple[WorkflowRunRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
    evals: tuple[EvalResult, ...],
    approvals: tuple[DashboardApprovalRequest, ...],
) -> tuple[DashboardWorkflowSummary, ...]:
    evidence_by_id = {record.id: record for record in evidence}
    eval_by_id = {result.id: result for result in evals}
    return tuple(
        _workflow_summary(record, evidence_by_id, eval_by_id, approvals)
        for record in sorted(records, key=lambda item: item.updated_at, reverse=True)
    )


def _workflow_summary(
    record: WorkflowRunRecord,
    evidence_by_id: dict[str, EvidenceRecord],
    eval_by_id: dict[str, EvalResult],
    approvals: tuple[DashboardApprovalRequest, ...],
) -> DashboardWorkflowSummary:
    evidence = evidence_by_id.get(record.evidence_id or "")
    eval_result = eval_by_id.get(record.eval_id or "")
    nodes = _workflow_nodes(record)
    return DashboardWorkflowSummary(
        id=record.id,
        goal=record.goal,
        status=record.status,
        current_node=record.current_node,
        capability_name=record.capability_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        elapsed_ms=_elapsed_ms(record.created_at, record.updated_at),
        runtime=record.config.runtime,
        model=record.config.model,
        progress_percent=_workflow_progress(record),
        completed_node_count=len(record.completed_nodes),
        total_node_count=len(ORCHESTRATOR_NODES),
        failed_node=record.failed_node,
        failure_reason=record.failure_reason,
        nodes=nodes,
        artifacts=DashboardArtifactIds(
            evidence_id=record.evidence_id,
            replay_id=record.replay_id,
            eval_id=record.eval_id,
            context_id=record.context_id,
            learning_id=record.learning_id,
        ),
        command_count=len(record.config.commands),
        harness_command_count=len(record.config.harness_commands),
        pending_approval_count=_pending_approval_count(record, approvals),
        cost_usd=_workflow_cost(evidence),
        latency_ms=_workflow_latency(evidence, eval_result),
        replay_command=_replay_command(record),
    )


def _workflow_nodes(record: WorkflowRunRecord) -> tuple[DashboardNode, ...]:
    return tuple(_workflow_node(record, node) for node in ORCHESTRATOR_NODES)


def _workflow_node(record: WorkflowRunRecord, node: str) -> DashboardNode:
    result = _latest_node(record, node)
    return DashboardNode(
        name=node,
        status=_workflow_node_status(record, node),
        message=result.message if result is not None else None,
        path=result.path if result is not None else None,
    )


def _workflow_node_status(
    record: WorkflowRunRecord,
    node: str,
) -> DashboardNodeStatus:
    if record.failed_node == node:
        return "fail"
    if record.current_node == node and record.status in ("running", "pending_review"):
        return "running"
    if node in record.completed_nodes:
        return "pass"
    return "pending"


def _latest_node(record: WorkflowRunRecord, node: str) -> WorkflowNodeResult | None:
    for result in reversed(record.nodes):
        if result.name == node:
            return result
    return None


def _workflow_progress(record: WorkflowRunRecord) -> int:
    if record.status == "completed":
        return 100
    return int((len(record.completed_nodes) / len(ORCHESTRATOR_NODES)) * 100)


def _workflow_cost(evidence: EvidenceRecord | None) -> float:
    if evidence is None:
        return 0.0
    return evidence.cost_metrics.total_cost_usd


def _workflow_latency(
    evidence: EvidenceRecord | None,
    eval_result: EvalResult | None,
) -> int:
    latency_ms = evidence.latency_metrics.total_ms if evidence is not None else 0
    if eval_result is None:
        return latency_ms
    return latency_ms + _command_latency(eval_result.command_executions)


def _pending_approval_count(
    record: WorkflowRunRecord,
    approvals: tuple[DashboardApprovalRequest, ...],
) -> int:
    target_ids = tuple(
        target_id
        for target_id in (record.evidence_id, record.replay_id, record.eval_id)
        if target_id is not None
    )
    return sum(approval.target_id in target_ids for approval in approvals)


def _replay_command(record: WorkflowRunRecord) -> str | None:
    if record.capability_name is None:
        return None
    return f"omf replay {record.capability_name}"


def _elapsed_ms(started_at: datetime, finished_at: datetime) -> int:
    return int((finished_at - started_at).total_seconds() * 1_000)


def _runtime_summaries(
    paths: DashboardPaths,
) -> tuple[DashboardRuntimeSummary, ...]:
    try:
        summary = run_runtime_inventory_workflow(
            RuntimeInventoryRequest(
                project=paths.project,
                home=paths.home,
                capabilities_dir=paths.capabilities_dir,
            ),
        )
    except ConformanceError:
        # A single misconfigured runtime must never blank the whole dashboard.
        return ()
    return tuple(
        DashboardRuntimeSummary(
            runtime=state.runtime,
            presence=state.presence,
            presence_detail=state.presence_detail,
            skill_installed=state.skill_installed,
            mcp_installed=state.mcp_installed,
            conformance_status=state.conformance_status,
            overall_status=state.overall_status,
            next_action=state.next_action,
            skill_path=state.skill_path,
            mcp_config_path=state.mcp_config_path,
        )
        for state in summary.runtimes
    )


def _capability_summaries(
    paths: DashboardPaths,
    eval_results: tuple[EvalResult, ...],
) -> tuple[DashboardCapabilitySummary, ...]:
    return tuple(
        _capability_summary(
            path=path,
            manifest=manifest,
            eval_results=eval_results,
        )
        for path, manifest in list_manifests(paths.capabilities_dir)
    )


def _capability_summary(
    *,
    path: Path,
    manifest: CapabilityManifest,
    eval_results: tuple[EvalResult, ...],
) -> DashboardCapabilitySummary:
    capability_evals = tuple(
        result for result in eval_results if result.capability_name == manifest.name
    )
    pass_count = sum(result.status == "pass" for result in capability_evals)
    patch_count = (
        len(manifest.patches.prompt)
        + len(manifest.patches.context)
        + len(manifest.patches.harness)
    )
    health_entry = health_entry_from_manifest(
        manifest=manifest,
        package_dir=path.parent,
        eval_results=eval_results,
    )
    portability_health = read_portability_health(path.parent)
    return DashboardCapabilitySummary(
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        status=manifest.status,
        runtime=manifest.runtime.name,
        model=manifest.runtime.model,
        tools=manifest.runtime.tools,
        network_policy=manifest.workflow_control.network_policy,
        required_checks=manifest.harness.required_checks,
        evaluation_results=manifest.evaluation_results,
        source_evidence_count=len(manifest.source_evidence_ids)
        if manifest.source_evidence_ids
        else 1,
        eval_count=len(capability_evals),
        pass_rate=pass_count / len(capability_evals) if capability_evals else 0.0,
        patch_count=patch_count,
        promotion_success_runs=(
            0
            if manifest.promotion_metrics is None
            else manifest.promotion_metrics.successful_evidence_count
        ),
        promotion_harness_pass_rate=(
            0.0
            if manifest.promotion_metrics is None
            else manifest.promotion_metrics.harness_pass_rate
        ),
        promotion_eval_pass_rate=(
            0.0
            if manifest.promotion_metrics is None
            else manifest.promotion_metrics.eval_pass_rate
        ),
        promotion_criteria_met=(
            False
            if manifest.promotion_metrics is None
            else manifest.promotion_metrics.criteria_met
        ),
        integrity_status=health_entry.integrity_status,
        next_action=health_entry.next_action,
        portability_export_status=portability_health.export_status,
        portability_import_status=portability_health.import_status,
        portability_validation_status=portability_health.validation_status,
        portability_export_count=portability_health.export_count,
        portability_import_count=portability_health.import_count,
        portability_target_validation_count=(
            portability_health.target_validation_count
        ),
        portability_targets=tuple(
            DashboardPortabilityTarget(
                target=target.target,
                validation_status=target.validation_status,
                portability_readiness_score=target.portability_readiness_score,
                eval_recorded=target.eval_recorded,
            )
            for target in portability_health.target_statuses
        ),
        manifest_path=str(path),
    )


def _replay_summary(record: ReplayRecord) -> DashboardReplaySummary:
    return DashboardReplaySummary(
        id=record.id,
        capability_name=record.capability_name,
        source_evidence_id=record.source_evidence_id,
        created_at=record.created_at,
        runtime=record.runtime.name,
        model=record.runtime.model,
        harness_status=record.harness.status,
        command_count=len(record.command_executions),
        latency_ms=_command_latency(record.command_executions),
    )


def _eval_summary(result: EvalResult) -> DashboardEvalSummary:
    return DashboardEvalSummary(
        id=result.id,
        capability_name=result.capability_name,
        replay_id=result.replay_id,
        status=result.status,
        created_at=result.created_at,
        check_count=len(result.checks),
        failure_count=len(result.failures),
        command_count=len(result.command_executions),
        latency_ms=_command_latency(result.command_executions),
    )


def _review_summary(record: HumanReviewRecord) -> DashboardReviewSummary:
    return DashboardReviewSummary(
        id=record.id,
        target_type=record.target_type,
        target_id=record.target_id,
        action=record.action,
        status=record.review.status,
        reviewer=record.review.reviewer,
        created_at=record.created_at,
        notes=record.review.notes,
        revision_request=record.review.revision_request,
    )


def _learning_patch_summary(
    decision: LearningPatchDecision,
) -> DashboardLearningPatchSummary:
    return DashboardLearningPatchSummary(
        id=decision.id,
        capability_name=decision.capability_name,
        learning_id=decision.learning_id,
        patch_kind=decision.patch_kind,
        decision=decision.decision,
        reviewer=decision.reviewer,
        created_at=decision.created_at,
        notes=decision.notes,
        pass_rate_delta=decision.pass_rate_delta,
        manifest_path=decision.manifest_path,
    )


def _approval_requests(
    evidence: tuple[EvidenceRecord, ...],
    replays: tuple[ReplayRecord, ...],
    evals: tuple[EvalResult, ...],
    reviews: tuple[HumanReviewRecord, ...],
    generated_at: datetime,
) -> tuple[DashboardApprovalRequest, ...]:
    reviewed_targets: set[tuple[ReviewTargetType, str]] = {
        (review.target_type, review.target_id)
        for review in reviews
        if review.action in ("approve", "reject", "revise")
    }
    return (
        *_approvals_for_evidence(evidence, reviewed_targets, generated_at),
        *_approvals_for_replays(replays, reviewed_targets, generated_at),
        *_approvals_for_evals(evals, reviewed_targets, generated_at),
    )


def _approvals_for_evidence(
    evidence: tuple[EvidenceRecord, ...],
    reviewed_targets: set[tuple[ReviewTargetType, str]],
    generated_at: datetime,
) -> tuple[DashboardApprovalRequest, ...]:
    return tuple(
        approval
        for record in evidence
        for approval in _approvals_for_commands(
            ApprovalCommandContext(
                target_type="evidence",
                target_id=record.id,
                source="capture command",
                created_at=record.created_at,
                generated_at=generated_at,
            ),
            record.command_executions,
            reviewed_targets,
        )
    )


def _approvals_for_replays(
    replays: tuple[ReplayRecord, ...],
    reviewed_targets: set[tuple[ReviewTargetType, str]],
    generated_at: datetime,
) -> tuple[DashboardApprovalRequest, ...]:
    return tuple(
        approval
        for record in replays
        for approval in _approvals_for_commands(
            ApprovalCommandContext(
                target_type="replay",
                target_id=record.id,
                source="replay command",
                created_at=record.created_at,
                generated_at=generated_at,
            ),
            record.command_executions,
            reviewed_targets,
        )
    )


def _approvals_for_evals(
    evals: tuple[EvalResult, ...],
    reviewed_targets: set[tuple[ReviewTargetType, str]],
    generated_at: datetime,
) -> tuple[DashboardApprovalRequest, ...]:
    return tuple(
        approval
        for result in evals
        for approval in _approvals_for_commands(
            ApprovalCommandContext(
                target_type="eval",
                target_id=result.id,
                source="harness command",
                created_at=result.created_at,
                generated_at=generated_at,
            ),
            result.command_executions,
            reviewed_targets,
        )
    )


def _approvals_for_commands(
    context: ApprovalCommandContext,
    commands: tuple[CommandExecution, ...],
    reviewed_targets: set[tuple[ReviewTargetType, str]],
) -> tuple[DashboardApprovalRequest, ...]:
    if (context.target_type, context.target_id) in reviewed_targets:
        return ()
    return tuple(
        _approval_request(
            context,
            index,
            command,
        )
        for index, command in enumerate(commands)
        if command.approval_required and not command.approved
    )


def _approval_request(
    context: ApprovalCommandContext,
    index: int,
    command: CommandExecution,
) -> DashboardApprovalRequest:
    age_seconds = int((context.generated_at - context.created_at).total_seconds())
    categories = tuple(str(category) for category in command.risk_categories)
    return DashboardApprovalRequest(
        id=f"{context.target_type}:{context.target_id}:{index}",
        target_type=context.target_type,
        target_id=context.target_id,
        source=context.source,
        created_at=context.created_at,
        age_seconds=age_seconds,
        timed_out=age_seconds >= APPROVAL_TIMEOUT_SECONDS,
        command=command.command,
        risk_categories=categories,
        reason="approval required for " + ", ".join(categories),
    )


def _events(
    workflows: tuple[DashboardWorkflowSummary, ...],
    approvals: tuple[DashboardApprovalRequest, ...],
    reviews: tuple[DashboardReviewSummary, ...],
    learning_patches: tuple[DashboardLearningPatchSummary, ...],
) -> tuple[DashboardEvent, ...]:
    events = (
        *_workflow_events(workflows),
        *_approval_events(approvals),
        *_review_events(reviews),
        *_learning_patch_events(learning_patches),
    )
    return tuple(
        sorted(events, key=lambda event: event.created_at, reverse=True)[:MAX_EVENTS],
    )


def _workflow_events(
    workflows: tuple[DashboardWorkflowSummary, ...],
) -> tuple[DashboardEvent, ...]:
    return tuple(_workflow_event(workflow) for workflow in workflows)


def _workflow_event(workflow: DashboardWorkflowSummary) -> DashboardEvent:
    if workflow.status == "failed":
        return DashboardEvent(
            id=f"workflow:{workflow.id}:failed",
            created_at=workflow.updated_at,
            severity="critical",
            kind="workflow_failed",
            title="Workflow failed",
            message=workflow.failure_reason or "workflow failed",
            workflow_id=workflow.id,
            node=workflow.failed_node,
        )
    if workflow.status == "pending_review":
        return DashboardEvent(
            id=f"workflow:{workflow.id}:pending_review",
            created_at=workflow.updated_at,
            severity="warning",
            kind="pending_review",
            title="Workflow pending review",
            message=workflow.current_node or "review required",
            workflow_id=workflow.id,
            node=workflow.current_node,
        )
    return DashboardEvent(
        id=f"workflow:{workflow.id}:{workflow.status}",
        created_at=workflow.updated_at,
        severity="info",
        kind="workflow_status",
        title=f"Workflow {workflow.status}",
        message=workflow.goal,
        workflow_id=workflow.id,
        node=workflow.current_node,
    )


def _approval_events(
    approvals: tuple[DashboardApprovalRequest, ...],
) -> tuple[DashboardEvent, ...]:
    return tuple(
        DashboardEvent(
            id=f"approval:{approval.id}",
            created_at=approval.created_at,
            severity="warning" if not approval.timed_out else "critical",
            kind="approval_required",
            title="Approval required",
            message=approval.reason,
            target_type=approval.target_type,
            target_id=approval.target_id,
        )
        for approval in approvals
    )


def _review_events(
    reviews: tuple[DashboardReviewSummary, ...],
) -> tuple[DashboardEvent, ...]:
    return tuple(
        DashboardEvent(
            id=f"review:{review.id}",
            created_at=review.created_at,
            severity=_review_severity(review),
            kind="human_review",
            title=f"Review {review.status}",
            message="; ".join(review.notes) if review.notes else review.action,
            target_type=review.target_type,
            target_id=review.target_id,
        )
        for review in reviews
    )


def _review_severity(review: DashboardReviewSummary) -> DashboardEventSeverity:
    if review.action in ("reject", "mark_unsafe"):
        return "critical"
    if review.action in ("revise", "add_context"):
        return "warning"
    return "info"


def _learning_patch_events(
    learning_patches: tuple[DashboardLearningPatchSummary, ...],
) -> tuple[DashboardEvent, ...]:
    return tuple(
        DashboardEvent(
            id=f"learning-patch:{patch.id}",
            created_at=patch.created_at,
            severity=_learning_patch_severity(patch),
            kind="learning_patch",
            title=f"Learning patch {patch.decision}",
            message=f"{patch.capability_name}: {patch.patch_kind}",
            target_type="learning-patch",
            target_id=patch.id,
        )
        for patch in learning_patches
    )


def _learning_patch_severity(
    patch: DashboardLearningPatchSummary,
) -> DashboardEventSeverity:
    if patch.decision == "rejected":
        return "warning"
    return "info"


def _metrics(
    workflows: tuple[DashboardWorkflowSummary, ...],
    capabilities: tuple[DashboardCapabilitySummary, ...],
    evals: tuple[DashboardEvalSummary, ...],
    approvals: tuple[DashboardApprovalRequest, ...],
    counts: DashboardMetricCounts,
) -> DashboardMetrics:
    return DashboardMetrics(
        workflow_count=len(workflows),
        running_count=_count_status(workflows, "running"),
        completed_count=_count_status(workflows, "completed"),
        failed_count=_count_status(workflows, "failed"),
        pending_review_count=_count_status(workflows, "pending_review"),
        capability_count=len(capabilities),
        harness_pass_rate=_pass_rate(evals),
        user_intervention_count=counts.user_intervention_count,
        pending_approval_count=len(approvals),
        regression_case_count=counts.regression_case_count,
        learning_patch_count=counts.learning_patch_count,
    )


def _count_status(
    workflows: tuple[DashboardWorkflowSummary, ...],
    status: str,
) -> int:
    return sum(workflow.status == status for workflow in workflows)


def _pass_rate(evals: tuple[DashboardEvalSummary, ...]) -> float:
    if not evals:
        return 0.0
    pass_count = sum(result.status == "pass" for result in evals)
    return pass_count / len(evals)


def _user_intervention_count(
    evidence: tuple[EvidenceRecord, ...],
    reviews: tuple[DashboardReviewSummary, ...],
) -> int:
    return sum(len(record.user_interventions) for record in evidence) + len(reviews)


def _capability_comparisons(
    workflows: tuple[DashboardWorkflowSummary, ...],
    evals: tuple[DashboardEvalSummary, ...],
) -> tuple[DashboardCapabilityComparison, ...]:
    capability_names = sorted(
        {
            *(
                workflow.capability_name
                for workflow in workflows
                if workflow.capability_name is not None
            ),
            *(result.capability_name for result in evals),
        },
    )
    return tuple(
        _capability_comparison(capability_name, workflows, evals)
        for capability_name in capability_names
    )


def _capability_comparison(
    capability_name: str,
    workflows: tuple[DashboardWorkflowSummary, ...],
    evals: tuple[DashboardEvalSummary, ...],
) -> DashboardCapabilityComparison:
    capability_workflows = tuple(
        workflow
        for workflow in workflows
        if workflow.capability_name == capability_name
    )
    capability_evals = tuple(
        result for result in evals if result.capability_name == capability_name
    )
    pass_count = sum(result.status == "pass" for result in capability_evals)
    fail_count = sum(result.status == "fail" for result in capability_evals)
    runtime_profiles = tuple(
        sorted(
            {
                _runtime_profile(workflow.runtime, workflow.model)
                for workflow in capability_workflows
            },
        ),
    )
    return DashboardCapabilityComparison(
        capability_name=capability_name,
        run_count=len(capability_workflows),
        eval_count=len(capability_evals),
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=pass_count / len(capability_evals) if capability_evals else 0.0,
        runtime_profiles=runtime_profiles,
        average_latency_ms=_average_latency(capability_workflows),
    )


def _runtime_profile(runtime: str, model: str | None) -> str:
    if model is None:
        return runtime
    return f"{runtime}:{model}"


def _average_latency(workflows: tuple[DashboardWorkflowSummary, ...]) -> int:
    if not workflows:
        return 0
    return int(sum(workflow.latency_ms for workflow in workflows) / len(workflows))


def _console_actions(
    approvals: tuple[DashboardApprovalRequest, ...],
    evals: tuple[DashboardEvalSummary, ...],
) -> tuple[DashboardConsoleAction, ...]:
    return (
        *tuple(_approval_action(approval) for approval in approvals),
        *tuple(
            _regression_action(eval_result)
            for eval_result in evals
            if eval_result.status == "fail"
        ),
    )


def _approval_action(approval: DashboardApprovalRequest) -> DashboardConsoleAction:
    return DashboardConsoleAction(
        kind="review",
        title=f"Review {approval.target_type} approval",
        command=(
            f"omf review {approval.target_type} {approval.target_id} approve "
            '--note "approved from dashboard"'
        ),
        target_type=approval.target_type,
        target_id=approval.target_id,
    )


def _regression_action(eval_result: DashboardEvalSummary) -> DashboardConsoleAction:
    case_id = f"eval_{eval_result.id[-8:]}"
    return DashboardConsoleAction(
        kind="regression_case",
        title=f"Create regression case for {eval_result.capability_name}",
        command=(
            f"omf regression-case {eval_result.capability_name} "
            f"--case-id {case_id} --check failed_eval_{eval_result.id[-8:]}"
        ),
        target_type="eval",
        target_id=eval_result.id,
    )


def _command_latency(commands: tuple[CommandExecution, ...]) -> int:
    return sum(command.duration_ms for command in commands)
