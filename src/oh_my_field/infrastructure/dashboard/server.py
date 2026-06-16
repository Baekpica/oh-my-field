import json
import secrets
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
CSRF_HEADER: Final = "X-OMF-Csrf-Token"
LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

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


def dashboard_html(csrf_token: str = "") -> str:
    return (
        dedent(
            """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>oh-my-field</title>
          <script>
            (function () {
              try {
                var stored = localStorage.getItem("omf-theme");
                if (stored !== "light" && stored !== "dark") {
                  stored = window.matchMedia
                    && matchMedia("(prefers-color-scheme: dark)").matches
                    ? "dark" : "light";
                }
                document.documentElement.dataset.theme = stored;
              } catch (e) {
                document.documentElement.dataset.theme = "light";
              }
            })();
          </script>
          <style>
            :root {
              color-scheme: light;
              --bg: #eceff5;
              --surface: #ffffff;
              --surface-2: #f7f9fc;
              --surface-3: #eef2f8;
              --ink: #131922;
              --ink-soft: #38434f;
              --muted: #69768a;
              --line: #e4e9f1;
              --line-strong: #d0d8e4;
              --accent: #0d9488;
              --accent-strong: #0f766e;
              --accent-ink: #ffffff;
              --accent-soft: #d4f2ec;
              --ok: #15803d;
              --ok-bg: #dcfce7;
              --ok-line: #a4e7bf;
              --bad: #be123c;
              --bad-bg: #ffe4e8;
              --bad-line: #fbc6cf;
              --warn: #b45309;
              --warn-bg: #fdf0cf;
              --warn-line: #f5d58a;
              --info: #1d4ed8;
              --info-bg: #dce6fc;
              --info-line: #bcd0f7;
              --shadow: 0 1px 2px rgba(15,23,42,.06),
                0 1px 3px rgba(15,23,42,.04);
              --shadow-lg: 0 10px 30px rgba(15,23,42,.10);
              --radius: 12px;
              --radius-sm: 8px;
              --pill: 999px;
              --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo,
                Consolas, monospace;
              --sans: ui-sans-serif, system-ui, -apple-system,
                BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            :root[data-theme="dark"] {
              color-scheme: dark;
              --bg: #0c1118;
              --surface: #141b25;
              --surface-2: #19212d;
              --surface-3: #1f2935;
              --ink: #e7edf5;
              --ink-soft: #c2ccd9;
              --muted: #8593a6;
              --line: #243040;
              --line-strong: #30404f;
              --accent: #2dd4bf;
              --accent-strong: #5eead4;
              --accent-ink: #042f2a;
              --accent-soft: #123b38;
              --ok: #4ade80;
              --ok-bg: #0f2f1f;
              --ok-line: #1f5538;
              --bad: #fb7185;
              --bad-bg: #3a1620;
              --bad-line: #6d2435;
              --warn: #fbbf24;
              --warn-bg: #392a10;
              --warn-line: #5e451a;
              --info: #7aa7ff;
              --info-bg: #15233f;
              --info-line: #2a4674;
              --shadow: 0 1px 2px rgba(0,0,0,.5);
              --shadow-lg: 0 14px 34px rgba(0,0,0,.55);
            }
            * { box-sizing: border-box; }
            html { scrollbar-gutter: stable; }
            body {
              margin: 0;
              color: var(--ink);
              background: var(--bg);
              font-family: var(--sans);
              font-size: 14px;
              line-height: 1.5;
              -webkit-font-smoothing: antialiased;
            }
            a { color: var(--accent-strong); }
            code, pre, .mono { font-family: var(--mono); }
            header {
              position: sticky;
              top: 0;
              z-index: 20;
              display: flex;
              align-items: center;
              gap: 18px;
              flex-wrap: wrap;
              padding: 12px 22px;
              background: color-mix(in srgb, var(--surface) 88%,
                transparent);
              backdrop-filter: blur(10px);
              border-bottom: 1px solid var(--line);
            }
            .brand { display: flex; align-items: center; gap: 11px; }
            .logo {
              display: grid;
              place-items: center;
              width: 34px;
              height: 34px;
              border-radius: 10px;
              color: var(--accent-ink);
              background: linear-gradient(135deg, var(--accent),
                var(--accent-strong));
              box-shadow: var(--shadow);
            }
            .brand-text { display: flex; flex-direction: column; }
            header h1 {
              margin: 0;
              font-size: 16px;
              font-weight: 700;
              letter-spacing: -.01em;
            }
            .brand .sub {
              color: var(--muted);
              font-size: 11.5px;
              letter-spacing: .04em;
              text-transform: uppercase;
            }
            .tabs {
              display: flex;
              gap: 2px;
              margin: 0 auto;
              padding: 4px;
              background: var(--surface-3);
              border: 1px solid var(--line);
              border-radius: var(--pill);
              overflow: auto;
            }
            .tab {
              padding: 7px 16px;
              border: 0;
              border-radius: var(--pill);
              background: transparent;
              color: var(--muted);
              font-size: 13.5px;
              font-weight: 600;
              white-space: nowrap;
              cursor: pointer;
              transition: background .15s, color .15s;
            }
            .tab:hover { color: var(--ink); }
            .tab.active {
              color: var(--ink);
              background: var(--surface);
              box-shadow: var(--shadow);
            }
            .header-actions {
              display: flex;
              align-items: center;
              gap: 12px;
            }
            .updated-wrap {
              display: inline-flex;
              align-items: center;
              gap: 7px;
              color: var(--muted);
              font-size: 12px;
              font-variant-numeric: tabular-nums;
            }
            .live-dot {
              width: 8px;
              height: 8px;
              border-radius: 50%;
              background: var(--ok);
              box-shadow: 0 0 0 0 color-mix(in srgb, var(--ok) 60%,
                transparent);
              animation: pulse 2s infinite;
            }
            @keyframes pulse {
              70% { box-shadow: 0 0 0 7px transparent; }
              100% { box-shadow: 0 0 0 0 transparent; }
            }
            .icon-btn {
              display: grid;
              place-items: center;
              width: 34px;
              height: 34px;
              padding: 0;
              font-size: 15px;
              border: 1px solid var(--line-strong);
              border-radius: 9px;
              background: var(--surface);
              color: var(--ink-soft);
              cursor: pointer;
            }
            .icon-btn:hover {
              background: var(--surface-3);
              color: var(--ink);
            }
            main {
              max-width: 1280px;
              margin: 0 auto;
              padding: 22px;
            }
            .panel[hidden] { display: none; }
            .panel { animation: fade .25s ease; }
            @keyframes fade {
              from { opacity: 0; transform: translateY(4px); }
              to { opacity: 1; transform: none; }
            }
            .grid2 {
              display: grid;
              grid-template-columns: minmax(360px, 1.15fr)
                minmax(300px, 0.85fr);
              gap: 18px;
            }
            section {
              background: var(--surface);
              border: 1px solid var(--line);
              border-radius: var(--radius);
              box-shadow: var(--shadow);
              overflow: hidden;
              margin-bottom: 18px;
            }
            section > h2 {
              margin: 0;
              padding: 13px 18px;
              font-size: 13px;
              font-weight: 700;
              letter-spacing: .02em;
              text-transform: uppercase;
              color: var(--ink-soft);
              background: var(--surface-2);
              border-bottom: 1px solid var(--line);
            }
            .content { padding: 16px 18px; }
            .metrics {
              display: grid;
              grid-template-columns: repeat(4, minmax(130px, 1fr));
              gap: 14px;
            }
            .metric {
              position: relative;
              padding: 14px 15px;
              border: 1px solid var(--line);
              border-radius: var(--radius-sm);
              background: var(--surface-2);
              transition: transform .15s, box-shadow .15s;
            }
            .metric:hover {
              transform: translateY(-2px);
              box-shadow: var(--shadow-lg);
            }
            .metric span {
              display: block;
              color: var(--muted);
              font-size: 11.5px;
              font-weight: 600;
              letter-spacing: .04em;
              text-transform: uppercase;
            }
            .metric b {
              display: block;
              margin-top: 7px;
              font-size: 26px;
              font-weight: 700;
              letter-spacing: -.02em;
              font-variant-numeric: tabular-nums;
            }
            table { width: 100%; border-collapse: collapse; font-size: 13px; }
            th, td {
              padding: 11px 12px;
              border-bottom: 1px solid var(--line);
              text-align: left;
              vertical-align: top;
            }
            thead th {
              position: sticky;
              top: 0;
              color: var(--muted);
              font-size: 11.5px;
              font-weight: 700;
              letter-spacing: .03em;
              text-transform: uppercase;
              background: var(--surface);
            }
            tbody tr { transition: background .12s; }
            tbody tr:last-child td { border-bottom: 0; }
            tr[data-run] { cursor: pointer; }
            tr[data-run]:hover, tbody tr:hover { background: var(--surface-2); }
            tr[data-run].selected {
              background: var(--accent-soft);
              box-shadow: inset 3px 0 0 var(--accent);
            }
            .tag {
              display: inline-block;
              padding: 2px 9px;
              border-radius: var(--pill);
              background: var(--surface-3);
              border: 1px solid var(--line);
              color: var(--ink-soft);
              font-size: 11.5px;
              font-weight: 600;
            }
            .pill {
              display: inline-flex;
              align-items: center;
              gap: 6px;
              padding: 3px 10px;
              border-radius: var(--pill);
              border: 1px solid var(--line);
              background: var(--surface-3);
              color: var(--ink-soft);
              font-size: 12px;
              font-weight: 600;
              white-space: nowrap;
            }
            .pill::before {
              content: "";
              width: 6px;
              height: 6px;
              border-radius: 50%;
              background: currentColor;
            }
            .pill.ok { color: var(--ok); background: var(--ok-bg);
              border-color: var(--ok-line); }
            .pill.bad { color: var(--bad); background: var(--bad-bg);
              border-color: var(--bad-line); }
            .pill.warn { color: var(--warn); background: var(--warn-bg);
              border-color: var(--warn-line); }
            .pill.info { color: var(--info); background: var(--info-bg);
              border-color: var(--info-line); }
            .pill.muted { color: var(--muted); }
            .pass { color: var(--ok); font-weight: 600; }
            .fail { color: var(--bad); font-weight: 600; }
            .warn { color: var(--warn); font-weight: 600; }
            .cards {
              display: grid;
              grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
              gap: 14px;
            }
            .card {
              display: flex;
              flex-direction: column;
              border: 1px solid var(--line);
              border-radius: var(--radius-sm);
              background: var(--surface-2);
              padding: 15px;
              transition: box-shadow .15s, border-color .15s;
            }
            .card:hover {
              box-shadow: var(--shadow-lg);
              border-color: var(--line-strong);
            }
            .card h3 {
              margin: 0 0 11px;
              font-size: 14.5px;
              font-weight: 700;
              display: flex;
              justify-content: space-between;
              align-items: center;
              gap: 8px;
            }
            .badge {
              font-size: 11px;
              font-weight: 700;
              letter-spacing: .03em;
              text-transform: uppercase;
              padding: 3px 10px;
              border-radius: var(--pill);
              border: 1px solid var(--line);
              color: var(--muted);
            }
            .badge.ready {
              color: var(--ok);
              background: var(--ok-bg);
              border-color: var(--ok-line);
            }
            .badge.partial {
              color: var(--warn);
              background: var(--warn-bg);
              border-color: var(--warn-line);
            }
            .badge.absent {
              color: var(--muted);
              background: var(--surface-3);
            }
            .checks { font-size: 13px; margin: 5px 0; color: var(--ink-soft); }
            .next {
              color: var(--muted);
              font-size: 12.5px;
              margin: 8px 0 4px;
              flex: 1;
            }
            .graph {
              display: grid;
              grid-template-columns: repeat(6, minmax(92px, 1fr));
              gap: 10px;
            }
            .node {
              min-height: 78px;
              padding: 11px;
              border: 1px solid var(--line);
              border-radius: var(--radius-sm);
              background: var(--surface-2);
              overflow-wrap: anywhere;
              position: relative;
            }
            .node strong {
              font-size: 13px;
              text-transform: capitalize;
            }
            .node .nstatus {
              display: block;
              margin: 4px 0 2px;
              font-size: 11.5px;
              font-weight: 600;
            }
            .node small { color: var(--muted); font-size: 11px; }
            .node.pass {
              border-color: var(--ok-line);
              background: var(--ok-bg);
            }
            .node.pass .nstatus { color: var(--ok); }
            .node.fail {
              border-color: var(--bad-line);
              background: var(--bad-bg);
            }
            .node.fail .nstatus { color: var(--bad); }
            .node.running {
              border-color: var(--info-line);
              background: var(--info-bg);
            }
            .node.running .nstatus { color: var(--info); }
            .progress {
              height: 7px;
              margin-top: 8px;
              background: var(--surface-3);
              border-radius: var(--pill);
              overflow: hidden;
            }
            .progress span {
              display: block;
              height: 100%;
              border-radius: var(--pill);
              background: linear-gradient(90deg, var(--accent),
                var(--accent-strong));
              transition: width .4s ease;
            }
            .event {
              padding: 11px 0 11px 13px;
              border-left: 3px solid var(--line-strong);
              border-bottom: 1px solid var(--line);
              margin-left: 2px;
            }
            .event:last-child { border-bottom: 0; }
            .event strong { font-size: 13.5px; }
            .event div { color: var(--ink-soft); margin: 2px 0; }
            .event small { color: var(--muted); font-size: 11.5px; }
            .event code {
              display: inline-block;
              margin-top: 4px;
              padding: 2px 7px;
              border-radius: 6px;
              background: var(--surface-3);
              font-size: 12px;
            }
            .event.info { border-left-color: var(--info); }
            .event.warning { border-left-color: var(--warn); }
            .event.critical { border-left-color: var(--bad); }
            .empty {
              padding: 26px 14px;
              text-align: center;
              color: var(--muted);
              font-size: 13px;
            }
            .controls {
              display: flex;
              gap: 10px;
              flex-wrap: wrap;
              align-items: center;
              margin-bottom: 14px;
            }
            .controls label {
              display: inline-flex;
              align-items: center;
              gap: 6px;
              font-size: 13px;
              color: var(--ink-soft);
            }
            button, .btn, select, input {
              font-family: inherit;
              font-size: 13px;
              min-height: 34px;
              border: 1px solid var(--line-strong);
              border-radius: var(--radius-sm);
              background: var(--surface);
              color: var(--ink);
            }
            select, input { padding: 0 10px; }
            input::placeholder { color: var(--muted); }
            button, .btn {
              padding: 0 13px;
              font-weight: 600;
              color: var(--ink-soft);
              cursor: pointer;
              transition: background .14s, border-color .14s, color .14s;
            }
            button:hover, .btn:hover {
              background: var(--surface-3);
              border-color: var(--muted);
              color: var(--ink);
            }
            .btn.primary {
              background: var(--accent);
              border-color: var(--accent-strong);
              color: var(--accent-ink);
            }
            .btn.primary:hover {
              background: var(--accent-strong);
              color: var(--accent-ink);
            }
            .btn.ghost { background: transparent; }
            .btn.ok {
              color: var(--ok);
              background: var(--ok-bg);
              border-color: var(--ok-line);
            }
            .btn.bad {
              color: var(--bad);
              background: var(--bad-bg);
              border-color: var(--bad-line);
            }
            :focus-visible {
              outline: 2px solid var(--accent);
              outline-offset: 2px;
            }
            .act { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
            pre {
              max-height: 280px;
              overflow: auto;
              margin: 10px 0 0;
              padding: 13px;
              background: #0b1220;
              color: #d7e0ee;
              border: 1px solid var(--line);
              border-radius: var(--radius-sm);
              font-size: 12px;
              line-height: 1.55;
              white-space: pre-wrap;
              overflow-wrap: anywhere;
            }
            footer {
              max-width: 1280px;
              margin: 0 auto;
              padding: 16px 22px 28px;
              color: var(--muted);
              font-size: 12px;
            }
            footer .mono { color: var(--ink-soft); }
            @media (max-width: 920px) {
              .grid2 { grid-template-columns: 1fr; }
              .metrics { grid-template-columns: repeat(2, 1fr); }
              .graph { grid-template-columns: repeat(2, 1fr); }
              .tabs { margin: 0; width: 100%; }
              header { gap: 12px; }
              section .content { overflow-x: auto; }
            }
            @media (prefers-reduced-motion: reduce) {
              * { animation: none !important; transition: none !important; }
            }
          </style>
        </head>
        <body>
          <header>
            <div class="brand">
              <span class="logo" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2.1"
                  stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="6" cy="6.5" r="2.4"></circle>
                  <circle cx="18" cy="9" r="2.4"></circle>
                  <circle cx="9.5" cy="18" r="2.4"></circle>
                  <path d="M8.1 7.4 15.7 8.2 M7.5 8.5 8.7 15.4"></path>
                </svg>
              </span>
              <div class="brand-text">
                <h1>oh-my-field</h1>
                <span class="sub">operating dashboard</span>
              </div>
            </div>
            <nav class="tabs" id="tabs" aria-label="Dashboard sections">
              <button class="tab active" data-tab="overview"
                aria-current="page">Overview</button>
              <button class="tab" data-tab="runtimes">Runtimes</button>
              <button class="tab" data-tab="capabilities">
                Capabilities</button>
              <button class="tab" data-tab="workflows">Workflows</button>
            </nav>
            <div class="header-actions">
              <span class="updated-wrap" title="Last snapshot">
                <span class="live-dot" aria-hidden="true"></span>
                <span id="updated">loading</span>
              </span>
              <button id="theme-toggle" class="icon-btn" type="button"
                onclick="toggleTheme()" aria-label="Toggle color theme">
                <span id="theme-icon" aria-hidden="true">
                  <svg width="15" height="15" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z">
                    </path>
                  </svg>
                </span>
              </button>
            </div>
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
                      <input id="search" placeholder="Filter runs&hellip;">
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
            Local API
            <span class="mono">/api/snapshot</span>
            <span class="mono">/api/runtimes</span>
            <span class="mono">/api/capabilities</span>
            <span class="mono">/api/learning-patches</span>
          </footer>
          <script>
            const CSRF_TOKEN = "__OMF_CSRF_TOKEN__";
            let snapshot = null;
            let selectedRunId = null;
            let activeTab = "overview";

            const byId = (id) => document.getElementById(id);
            const pct = (value) => `${Math.round(value)}%`;
            const shortId = (value) => value ? value.slice(0, 18) : "";
            const fmtTime = (value) => String(value == null ? "" : value)
              .replace("T", " ").replace("Z", " UTC");
            const mark = (ok) => ok
              ? '<span class="pass">&#10003;</span>'
              : '<span class="fail">&#10007;</span>';
            const esc = (value) => String(value == null ? "" : value)
              .replace(/&/g, "&amp;").replace(/</g, "&lt;")
              .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
            const STATUS_KIND = {
              pass: "ok", completed: "ok", ready: "ok", validated: "ok",
              approved: "ok", verified: "ok", active: "ok",
              fail: "bad", failed: "bad", rejected: "bad",
              needs_adaptation: "bad",
              running: "info",
              pending: "warn", pending_review: "warn", partial: "warn",
              needs_validation: "warn", draft: "warn"
            };
            const kindOf = (value) =>
              STATUS_KIND[String(value == null ? "" : value).toLowerCase()]
              || "muted";
            const pill = (value) =>
              `<span class="pill ${kindOf(value)}">${esc(value)}</span>`;
            const SVG_OPEN =
              '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"'
              + ' stroke="currentColor" stroke-width="2"'
              + ' stroke-linecap="round" stroke-linejoin="round">';
            const ICON_MOON = SVG_OPEN
              + '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z">'
              + "</path></svg>";
            const ICON_SUN = SVG_OPEN
              + '<circle cx="12" cy="12" r="4"></circle>'
              + '<path d="M12 3v1.5M12 19.5V21M3 12h1.5M19.5 12H21'
              + 'M5.6 5.6l1 1M17.4 17.4l1 1M18.4 5.6l-1 1M6.6 17.4l-1 1">'
              + "</path></svg>";

            function applyThemeIcon() {
              const dark = document.documentElement.dataset.theme === "dark";
              const icon = byId("theme-icon");
              const btn = byId("theme-toggle");
              if (icon) icon.innerHTML = dark ? ICON_SUN : ICON_MOON;
              if (btn) btn.setAttribute("aria-label", dark
                ? "Switch to light theme" : "Switch to dark theme");
            }

            function toggleTheme() {
              const root = document.documentElement;
              const next = root.dataset.theme === "dark" ? "light" : "dark";
              root.dataset.theme = next;
              try { localStorage.setItem("omf-theme", next); } catch (e) {}
              applyThemeIcon();
            }

            async function postJson(url, payload) {
              const response = await fetch(url, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-OMF-Csrf-Token": CSRF_TOKEN
                },
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
              byId("updated").textContent = fmtTime(snapshot.generated_at);
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
                const on = tab.dataset.tab === name;
                tab.classList.toggle("active", on);
                if (on) tab.setAttribute("aria-current", "page");
                else tab.removeAttribute("aria-current");
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
                `<div class="event warning"><strong class="warn">Approval` +
                ` required</strong><div>${esc(item.reason)}</div>` +
                `<code>${esc(item.command)}</code></div>`
              ));
              failed.forEach((run) => parts.push(
                `<div class="event critical"><strong class="fail">Workflow` +
                ` failed</strong><div>${esc(run.goal)}</div>` +
                `<small>${esc(run.failure_reason || "")}</small></div>`
              ));
              byId("attention").innerHTML = parts.length
                ? parts.join("")
                : '<div class="empty">Nothing needs attention.</div>';
            }

            function renderRuntimes() {
              const rows = snapshot.runtimes || [];
              if (rows.length === 0) {
                byId("runtime-cards").innerHTML =
                  '<div class="empty">No runtime information available.' +
                  "</div>";
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
                    <button class="btn ghost"
                      onclick="runtimeSkill('${esc(r.runtime)}', false)">
                      Preview skill</button>
                    <button class="btn primary"
                      onclick="runtimeSkill('${esc(r.runtime)}', true)">
                      Install skill</button>
                    <button class="btn ghost"
                      onclick="runtimeMcp('${esc(r.runtime)}', false)">
                      Preview MCP</button>
                    <button class="btn primary"
                      onclick="runtimeMcp('${esc(r.runtime)}', true)">
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
              if (rows.length === 0) {
                byId("workflow-rows").innerHTML =
                  '<tr><td colspan="4"><div class="empty">' +
                  "No matching runs.</div></td></tr>";
                return;
              }
              byId("workflow-rows").innerHTML = rows.map((run) =>
                `<tr data-run="${run.id}" onclick="selectRun('${run.id}')"` +
                `${run.id === selectedRunId ? ' class="selected"' : ""}>
                  <td><span class="mono">${shortId(run.id)}</span><br>` +
                  `${esc(run.goal)}</td>
                  <td>${pill(run.status)}</td>
                  <td>${esc(run.capability_name || "")}<br>` +
                  `<small>${esc(run.runtime)}</small></td>
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
                byId("selected-run").innerHTML =
                  '<div class="empty">No workflow selected.</div>';
                byId("graph-nodes").innerHTML = "";
                return;
              }
              byId("selected-run").innerHTML =
                `<span class="mono">${shortId(run.id)}</span> ` +
                `${pill(run.status)} &middot; ${pct(run.progress_percent)}`;
              byId("graph-nodes").innerHTML = run.nodes.map((node) =>
                `<div class="node ${node.status}">
                  <strong>${esc(node.name)}</strong>
                  <span class="nstatus">${esc(node.status)}</span>
                  <small>${esc(node.message || "")}</small>
                </div>`
              ).join("");
            }

            function renderApprovals() {
              const approvals = snapshot.approvals;
              if (approvals.length === 0) {
                byId("approval-list").innerHTML =
                  '<div class="empty">No pending approvals.</div>';
                return;
              }
              byId("approval-list").innerHTML = approvals.map((item) =>
                `<div class="event warning">
                  <strong>${esc(item.target_type)} ` +
                  `${shortId(item.target_id)}</strong>
                  <div>${esc(item.reason)}</div>
                  <code>${esc(item.command)}</code>
                  <div class="act">
                  <button class="btn ok" onclick="review('${item.target_type}',
                    '${item.target_id}', 'approve')">Approve</button>
                  <button class="btn bad" onclick="review('${item.target_type}',
                    '${item.target_id}', 'reject')">Reject</button>
                  <button class="btn ghost" onclick="revise(` +
                    `'${item.target_type}',
                    '${item.target_id}')">Revise</button>
                  </div>
                </div>`
              ).join("");
            }

            function renderCapabilities() {
              const rows = snapshot.capabilities || [];
              if (rows.length === 0) {
                byId("capability-rows").innerHTML =
                  '<tr><td colspan="4"><div class="empty">' +
                  "No capabilities.</div></td></tr>";
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
                  <td><strong>${esc(item.name)}</strong><br>` +
                  `${pill(item.status)}</td>
                  <td>${pill(item.integrity_status)}<br>` +
                  `<small>${pct(item.pass_rate)} pass</small></td>
                  <td><span class="mono">${port}</span>` +
                  `<br><small>${targets}</small></td>
                  <td><div class="act">` +
                  `<button class="btn primary" onclick="exportCapability(` +
                  `'${esc(item.name)}')">Export</button>
                    <button class="btn ghost" onclick="validateCapability(` +
                    `'${esc(item.name)}', '${rt}')">Validate</button>` +
                  `</div></td>
                </tr>`;
              }).join("");
            }

            function renderLearningPatches() {
              const rows = snapshot.learning_patches || [];
              if (rows.length === 0) {
                byId("learning-patch-rows").innerHTML =
                  '<tr><td colspan="4"><div class="empty">' +
                  "No learning patches.</div></td></tr>";
                return;
              }
              byId("learning-patch-rows").innerHTML = rows.map((item) =>
                `<tr>
                  <td><span class="mono">${shortId(item.id)}</span><br>` +
                  `${esc(item.capability_name)}
                    <br><span class="tag">${esc(item.patch_kind)}</span></td>
                  <td>${pill(item.decision)}</td>
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
              const events = snapshot.events
                .filter((event) => enabled[event.severity]);
              if (events.length === 0) {
                byId("event-list").innerHTML =
                  '<div class="empty">No events to show.</div>';
                return;
              }
              byId("event-list").innerHTML = events
                .map((event) =>
                  `<div class="event ${event.severity}">
                    <strong>${esc(event.title)}</strong>
                    <div>${esc(event.message)}</div>
                    <small>${fmtTime(event.created_at)}</small>
                  </div>`
                ).join("");
            }

            function renderComparisons() {
              if (snapshot.comparisons.length === 0) {
                byId("comparison-rows").innerHTML =
                  '<tr><td colspan="5"><div class="empty">' +
                  "No execution history.</div></td></tr>";
                return;
              }
              byId("comparison-rows").innerHTML =
                snapshot.comparisons.map((item) =>
                  `<tr>
                    <td><strong>${esc(item.capability_name)}</strong></td>
                    <td>${item.run_count}</td>
                    <td>${item.eval_count}</td>
                    <td>${pct(item.pass_rate)}</td>
                    <td><small>${esc(item.runtime_profiles.join(", "))}` +
                    `</small></td>
                  </tr>`
                ).join("");
            }

            function selectedRun() {
              return snapshot.workflows.find((r) => r.id === selectedRunId);
            }

            function selectRun(runId) {
              selectedRunId = runId;
              renderWorkflows();
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
            applyThemeIcon();
            refresh();
            setInterval(refresh, 2000);
          </script>
        </body>
        </html>
        """,
        )
        .strip()
        .replace("__OMF_CSRF_TOKEN__", csrf_token)
    )


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
        # Per-process secret that gates mutating POST routes against CSRF.
        self.csrf_token = secrets.token_urlsafe(32)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "oh-my-field-dashboard/0.1"

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._send_error(HTTPStatus.FORBIDDEN, "host not allowed")
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_text(
                dashboard_html(self._csrf_token()),
                "text/html; charset=utf-8",
            )
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
        if self._reject_unsafe_post():
            return
        body = self._read_body()
        if body is None:
            return
        handler(body)

    def _csrf_token(self) -> str:
        return _dashboard_server(self.server).csrf_token

    def _bound_port(self) -> int:
        return cast("tuple[str, int]", self.server.server_address)[1]

    def _host_allowed(self) -> bool:
        host_header = self.headers.get("Host")
        if host_header is None:
            # Pre-1.1 clients omit Host; only browsers (which always send it)
            # are the CSRF/rebinding threat, so allow header-less callers.
            return True
        return _hostname(host_header) in LOOPBACK_HOSTS

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urlparse(origin)
        if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
            return False
        return parsed.port in (None, self._bound_port())

    def _reject_unsafe_post(self) -> bool:
        """Return True (and send 403) when a POST fails a safety check."""
        if not self._host_allowed():
            self._send_error(HTTPStatus.FORBIDDEN, "host not allowed")
            return True
        if not self._origin_allowed():
            self._send_error(HTTPStatus.FORBIDDEN, "cross-origin POST rejected")
            return True
        token = self.headers.get(CSRF_HEADER)
        if token is None or not secrets.compare_digest(token, self._csrf_token()):
            self._send_error(HTTPStatus.FORBIDDEN, "missing or invalid CSRF token")
            return True
        return False

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


def _hostname(host_header: str) -> str:
    """Return the hostname from a ``Host`` header, dropping any port."""
    value = host_header.strip()
    if value.startswith("["):
        return value[: value.index("]") + 1] if "]" in value else value
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


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
