from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityExportBundle,
    CapabilityManifest,
    CapturedTextFile,
    ContextBundle,
    ContextPolicy,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    LearningExport,
    PromotionCriteria,
    ReflectionReport,
    RuntimeInfo,
    WorkflowManifest,
    WorkflowNodeResult,
    WorkflowRunConfig,
    WorkflowRunRecord,
)
from oh_my_field.storage import (
    load_workflow_run,
    write_context_bundle,
    write_eval_result,
    write_evidence,
    write_learning_export,
    write_manifest,
    write_reflection_report,
    write_workflow_run,
)


class InspectOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: str
    target_id: str
    path: str
    status: str | None = None
    payload: dict[str, object]


class ExportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: str
    export_path: str
    capability_name: str
    eval_count: int
    context_count: int
    learning_count: int
    reflection_count: int


class RollbackOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    run_path: str
    status: str
    current_node: str
    completed_nodes: tuple[str, ...]
    cleared_artifacts: tuple[str, ...]


def test_inspect_reads_evidence_summary(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence = make_evidence_record()
    write_evidence(evidence, evidence_dir)

    result = CliRunner().invoke(
        app,
        [
            "inspect",
            "evidence",
            evidence.id,
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0
    output = InspectOutput.model_validate_json(result.stdout)
    assert output.target_type == "evidence"
    assert output.target_id == evidence.id
    assert output.status == "pass"
    assert output.payload["goal"] == "triage repo issue"
    assert output.payload["file_count"] == 1


def test_export_requires_approval_and_writes_capability_bundle(
    tmp_path: Path,
) -> None:
    dirs = ArtifactDirs.from_root(tmp_path)
    evidence = make_evidence_record()
    manifest = make_manifest()
    eval_result = make_eval_result()
    context_bundle = make_context_bundle()
    learning_export = make_learning_export()
    reflection_report = make_reflection_report()
    write_evidence(evidence, dirs.evidence)
    write_manifest(manifest, dirs.capabilities)
    write_eval_result(eval_result, dirs.evals)
    write_context_bundle(context_bundle, dirs.context)
    write_learning_export(learning_export, dirs.learning)
    write_reflection_report(reflection_report, dirs.reflections)

    blocked = CliRunner().invoke(
        app,
        [
            "export",
            manifest.name,
            *dirs.export_args(),
        ],
    )

    assert blocked.exit_code != 0
    assert "--approve-export" in blocked.stderr

    result = CliRunner().invoke(
        app,
        [
            "export",
            manifest.name,
            "--approve-export",
            *dirs.export_args(),
        ],
    )

    assert result.exit_code == 0
    output = ExportOutput.model_validate_json(result.stdout)
    bundle = CapabilityExportBundle.model_validate_json(
        Path(output.export_path).read_text(encoding="utf-8"),
    )
    assert output.capability_name == manifest.name
    assert output.eval_count == 1
    assert output.context_count == 1
    assert output.learning_count == 1
    assert output.reflection_count == 1
    assert bundle.manifest == manifest
    assert bundle.source_evidence == evidence
    assert bundle.eval_results == (eval_result,)
    assert bundle.context_bundles == (context_bundle,)
    assert bundle.learning_exports == (learning_export,)
    assert bundle.reflection_reports == (reflection_report,)


def test_rollback_resets_workflow_to_requested_node(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "workflows"
    run = make_workflow_run()
    write_workflow_run(run, workflow_dir)

    result = CliRunner().invoke(
        app,
        [
            "rollback",
            run.id,
            "--to-node",
            "execute_replay",
            "--reason",
            "rerun command with approval",
            "--workflow-dir",
            str(workflow_dir),
        ],
    )

    assert result.exit_code == 0
    output = RollbackOutput.model_validate_json(result.stdout)
    rolled_back = load_workflow_run(run.id, workflow_dir)
    assert output.status == "pending_review"
    assert output.current_node == "execute_replay"
    assert output.completed_nodes == (
        "observe_capture",
        "structure_promote",
        "context_pack",
    )
    assert output.cleared_artifacts == ("replay_id", "eval_id", "learning_id")
    assert rolled_back.replay_id is None
    assert rolled_back.eval_id is None
    assert rolled_back.learning_id is None
    assert rolled_back.context_id == "20260602T010207Z-facefeed"


class ArtifactDirs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capabilities: Path
    evidence: Path
    evals: Path
    context: Path
    learning: Path
    reflections: Path
    exports: Path

    @classmethod
    def from_root(cls, root: Path) -> "ArtifactDirs":
        return cls(
            capabilities=root / "capabilities",
            evidence=root / "evidence",
            evals=root / "evals",
            context=root / "context",
            learning=root / "learning",
            reflections=root / "reflections",
            exports=root / "exports",
        )

    def export_args(self) -> list[str]:
        return [
            "--capabilities-dir",
            str(self.capabilities),
            "--evidence-dir",
            str(self.evidence),
            "--eval-dir",
            str(self.evals),
            "--context-dir",
            str(self.context),
            "--learning-dir",
            str(self.learning),
            "--reflection-dir",
            str(self.reflections),
            "--export-dir",
            str(self.exports),
        ]


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
        workflow=WorkflowManifest(graph="langgraph", nodes=("parse_goal",)),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def make_eval_result() -> EvalResult:
    return EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        status="pass",
        checks=(EvalCheck(name="schema_valid", status="pass", message="ok"),),
    )


def make_context_bundle() -> ContextBundle:
    return ContextBundle(
        id="20260602T010207Z-facefeed",
        created_at=datetime(2026, 6, 2, 1, 2, 7, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        required_context=(
            CapturedTextFile(
                role="context",
                path="repo.md",
                content="Repository constraints.",
                size_bytes=23,
                sha256="0" * 64,
            ),
        ),
        policy=ContextPolicy(required=("repo.md",)),
    )


def make_learning_export() -> LearningExport:
    return LearningExport(
        id="20260602T010206Z-baddcafe",
        created_at=datetime(2026, 6, 2, 1, 2, 6, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        prompt_improvement_candidates=("run tests",),
    )


def make_reflection_report() -> ReflectionReport:
    return ReflectionReport(
        id="20260602T010209Z-aabbccdd",
        created_at=datetime(2026, 6, 2, 1, 2, 9, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        eval_id="20260602T010204Z-feedface",
        failure_categories=("rubric",),
        retry_strategy="Retry after improving rubric evidence.",
    )


def make_workflow_run() -> WorkflowRunRecord:
    return WorkflowRunRecord(
        id="20260602T010208Z-1234abcd",
        created_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        updated_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        goal="triage repo issue",
        status="completed",
        completed_nodes=(
            "observe_capture",
            "structure_promote",
            "context_pack",
            "execute_replay",
            "evaluate_harness",
            "learn_export",
        ),
        config=WorkflowRunConfig(
            capability_name="repo_issue_triage",
            description="GitHub issue triage capability",
            version="0.1.0",
            field="local",
            runtime="codex",
            command_cwd=".",
            command_timeout_seconds=60,
            evidence_dir=".omf/evidence",
            capabilities_dir="capabilities",
            replay_dir=".omf/replays",
            eval_dir=".omf/evals",
            context_dir=".omf/context",
            learning_dir=".omf/learning",
        ),
        nodes=(
            WorkflowNodeResult(name="observe_capture", status="pass", message="ok"),
            WorkflowNodeResult(name="structure_promote", status="pass", message="ok"),
            WorkflowNodeResult(name="context_pack", status="pass", message="ok"),
            WorkflowNodeResult(name="execute_replay", status="pass", message="ok"),
            WorkflowNodeResult(name="evaluate_harness", status="pass", message="ok"),
            WorkflowNodeResult(name="learn_export", status="pass", message="ok"),
        ),
        evidence_id="20260602T010203Z-deadbeef",
        capability_name="repo_issue_triage",
        replay_id="20260602T010204Z-feedface",
        eval_id="20260602T010205Z-cafebabe",
        context_id="20260602T010207Z-facefeed",
        learning_id="20260602T010206Z-baddcafe",
    )
