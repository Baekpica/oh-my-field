from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    ContextBundle,
    ContextPolicy,
    ContextSource,
    EvidenceRecord,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    WorkflowManifest,
)
from oh_my_field.storage import write_evidence, write_manifest


class ContextOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_id: str
    context_path: str
    capability_name: str
    required_count: int
    optional_count: int


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        input_context=("repo.md",),
        files=(
            CapturedTextFile(
                role="context",
                path="repo.md",
                content="Repository constraints.",
                size_bytes=23,
                sha256="0" * 64,
            ),
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="1" * 64,
            ),
            CapturedTextFile(
                role="artifact",
                path="secrets/token.txt",
                content="do not include",
                size_bytes=14,
                sha256="2" * 64,
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
        context=ContextPolicy(
            required=("repo.md",),
            optional=("prompt.md", "secrets/token.txt"),
            forbidden=("secrets/",),
            sources=(
                ContextSource(
                    name="repo_doc",
                    type="docs",
                    location="repo.md",
                    freshness="captured",
                    priority=1,
                ),
            ),
            source_priority=("evidence", "repository"),
            evidence_recall_strategy="prefer prior successful evidence",
        ),
        workflow=WorkflowManifest(graph="langgraph", nodes=("collect_context",)),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )


def test_context_builds_context_bundle_from_capability_policy(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    context_dir = tmp_path / "context"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "context",
            manifest.name,
            "--include-optional",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--context-dir",
            str(context_dir),
        ],
    )

    assert result.exit_code == 0
    output = ContextOutput.model_validate_json(result.stdout)
    bundle = ContextBundle.model_validate_json(
        Path(output.context_path).read_text(encoding="utf-8"),
    )
    assert output.required_count == 1
    assert output.optional_count == 1
    assert bundle.required_context[0].path == "repo.md"
    assert bundle.optional_context[0].path == "prompt.md"
    assert bundle.pack_plan is not None
    assert bundle.pack_plan.token_estimate > 0
    assert bundle.pack_plan.required[0].source == "repo_doc"
    assert bundle.pack_plan.required[0].source_type == "docs"
    assert bundle.pack_plan.required[0].priority == 1
    assert bundle.pack_plan.recall_notes == (
        "evidence_recall: prefer prior successful evidence",
    )
    assert bundle.pack_plan.excluded[0].path == "secrets/token.txt"
    assert bundle.pack_plan.excluded[0].reason == (
        "forbidden by capability context policy"
    )
    assert bundle.integrity_chain[-1].artifact_type == "context"


def test_context_filters_optional_context_and_writes_compressed_copy(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    context_dir = tmp_path / "context"
    evidence = make_evidence_record()
    manifest = make_manifest()
    write_evidence(evidence, evidence_dir)
    write_manifest(manifest, capabilities_dir)

    result = CliRunner().invoke(
        app,
        [
            "context",
            manifest.name,
            "--include-optional",
            "--query",
            "Find",
            "--max-chars",
            "4",
            "--capabilities-dir",
            str(capabilities_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--context-dir",
            str(context_dir),
        ],
    )

    assert result.exit_code == 0
    output = ContextOutput.model_validate_json(result.stdout)
    bundle = ContextBundle.model_validate_json(
        Path(output.context_path).read_text(encoding="utf-8"),
    )
    assert output.required_count == 1
    assert output.optional_count == 1
    assert bundle.summaries
    assert [file.content for file in bundle.compressed_context] == ["Repo", "Find"]
    assert bundle.pack_plan is not None
    assert bundle.pack_plan.required[0].compressed
    assert bundle.pack_plan.optional[0].matched_query
