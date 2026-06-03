from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from oh_my_field.models import (
    CapabilityManifest,
    CapturedTextFile,
    ContextItem,
    ContextPackPlan,
    ContextSource,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    FieldManifest,
    FieldPolicy,
    HarnessResult,
    PromotionCriteria,
    ReplayRecord,
    RuntimeInfo,
    WorkflowManifest,
)

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


def test_evidence_record_accepts_valid_manual_inputs() -> None:
    record = EvidenceRecord(
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
        feedback=("looks reusable",),
        harness=HarnessResult(status="pass", checks=("schema_valid",), failures=()),
    )

    assert record.goal == "triage repo issue"
    assert record.files[0].role == "prompt"


def test_evidence_record_rejects_extra_fields() -> None:
    payload: dict[str, JsonValue] = {
        "id": "20260602T010203Z-deadbeef",
        "created_at": "2026-06-02T01:02:03Z",
        "goal": "triage repo issue",
        "field": "local",
        "runtime": {"name": "codex", "model": None},
        "files": [],
        "feedback": [],
        "harness": {"status": "pass", "checks": ["schema_valid"], "failures": []},
        "unexpected": "nope",
    }

    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(payload)


def test_capability_manifest_rejects_invalid_name() -> None:
    with pytest.raises(ValidationError):
        CapabilityManifest(
            name="Repo-Issue",
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
            runtime=RuntimeInfo(name="codex", model=None),
            promotion_criteria=PromotionCriteria(
                min_success_runs=3,
                max_human_intervention_rate=0.3,
                required_harness_pass_rate=0.9,
            ),
        )


def test_replay_and_eval_models_accept_valid_payloads() -> None:
    workflow = WorkflowManifest(
        graph="langgraph",
        nodes=("load_evidence", "write_capability"),
    )
    harness = HarnessResult(
        status="pass",
        checks=("schema_valid",),
        failures=(),
    )
    runtime = RuntimeInfo(name="codex", model="gpt-5.5")

    replay = ReplayRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        source_goal="triage repo issue",
        workflow=workflow,
        harness=harness,
        runtime=runtime,
    )
    result = EvalResult(
        id="20260602T010204Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue",
        source_evidence_id="20260602T010203Z-deadbeef",
        replay_id=replay.id,
        status="pass",
        checks=(EvalCheck(name="schema_valid", status="pass", message="ok"),),
        failures=(),
    )

    assert replay.capability_name == "repo_issue"
    assert result.checks[0].name == "schema_valid"


def test_field_manifest_and_context_pack_plan_are_first_class_models() -> None:
    field = FieldManifest(
        name="infra_ops",
        description="Local infra operations",
        sources=(
            ContextSource(
                name="runbook",
                type="docs",
                location="runbooks/",
                priority=1,
            ),
        ),
        policies=FieldPolicy(
            network="internal_only",
            forbidden_context=(".env", "secrets/"),
        ),
    )
    plan = ContextPackPlan(
        required=(
            ContextItem(
                path="runbooks/deploy.md",
                source="runbook",
                reason="required by field policy",
                token_estimate=20,
            ),
        ),
        token_estimate=20,
        compression_strategy="none",
        source_priority=("runbook",),
    )

    assert field.policies.network == "internal_only"
    assert field.sources[0].type == "docs"
    assert plan.required[0].reason == "required by field policy"
