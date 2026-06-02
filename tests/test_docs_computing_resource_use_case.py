from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_and_product_vision_link_the_use_case() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/use-cases/computing-resource-workflow.md" in readme_text
    assert "docs/use-cases/local-cli-lifecycle.md" in readme_text
    assert "Do not ship or document a feature as working unless it actually ran" in readme_text

    product_vision = (ROOT / "oh-my-field.md").read_text(encoding="utf-8")
    for section in (
        "## 1. Observe",
        "## 2. Structure",
        "## 3. Harness",
        "## 4. Execute",
        "## 5. Evaluate",
        "## 6. Promote",
        "## 7. Learn",
    ):
        assert section in product_vision
    assert "## Computing Resource Workflow Agent화" in product_vision
    assert "실제로 실행·검증된 evidence가 없는 수치" in product_vision
    assert "`omf capture`" in product_vision
    assert "`omf promote`" in product_vision
    assert "`omf replay`" in product_vision
    assert "`omf eval`" in product_vision
    assert "`omf list`" in product_vision
    assert "`omf inspect`" in product_vision
    assert "`omf review`" in product_vision
    assert "`omf regress`" in product_vision
    assert "`omf learn`" in product_vision
    assert "`omf search`" in product_vision
    assert "`omf capture --check`" in product_vision
    assert "Git 기반 작업 이력" in product_vision
    assert "현재 MVP에서 검증된 범위는 local store JSON artifact" in product_vision
    assert "status, validated flag" in product_vision
    assert "local JSONL learning candidate" in product_vision
    assert "실제 model training/fine-tuning은 구현된 기능으로 주장하지 않음" in product_vision
    assert "모델 학습까지 수직적으로 연결" not in product_vision


def test_example_readme_documents_local_evidence_outputs_and_platform_effects() -> None:
    example_readme = (
        ROOT / "examples" / "computing-resource-workflow" / "README.md"
    ).read_text(encoding="utf-8")
    for section in (
        "## Inputs",
        "## Evidence",
        "## Outputs",
        "## As-Is",
        "## To-Be",
        "## Platform Effects",
    ):
        assert section in example_readme
    assert "evidence/local-execution.json" in example_readme
    assert "workflow_trace" in example_readme
    assert "Workflow Trace" in example_readme
    assert "GPU usage or cost" in example_readme
    assert "--write-report" in example_readme

    use_case_text = (
        ROOT / "docs" / "use-cases" / "computing-resource-workflow.md"
    ).read_text(encoding="utf-8")
    assert "## 플랫폼 / 런타임 효과" in use_case_text
    assert "## 매우 중요한 원칙" in use_case_text
    assert "evidence/local-execution.json" in use_case_text
    assert "workflow_trace" in use_case_text
    assert "Workflow Trace" in use_case_text
    assert "실제로 동작이 입증되지 않은 값" in use_case_text


def test_local_cli_lifecycle_doc_matches_implemented_commands() -> None:
    lifecycle_doc = (ROOT / "docs" / "use-cases" / "local-cli-lifecycle.md").read_text(
        encoding="utf-8"
    )
    for command in (
        "omf capture",
        "omf promote",
        "omf replay",
        "omf eval",
        "omf list",
        "omf inspect",
        "omf review",
        "omf regress",
        "omf learn",
        "omf search",
    ):
        assert command in lifecycle_doc
    assert "artifact SHA-256" in lifecycle_doc
    assert "shell syntax such as redirection" in lifecycle_doc
    assert "source evidence SHA-256" in lifecycle_doc
    assert "source evidence hash verification" in lifecycle_doc
    assert "recorded artifact hash verification" in lifecycle_doc
    assert "verifies recorded artifact existence, SHA-256, and size" in lifecycle_doc
    assert "manifest/evidence hash verification" in lifecycle_doc
    assert "embedded replay verification" in lifecycle_doc
    assert (
        "Replay first verifies that the capability manifest passes `omf inspect`"
        in lifecycle_doc
    )
    assert (
        "Eval first verifies that the capability manifest passes `omf inspect`"
        in lifecycle_doc
    )
    assert "Invalid manifests fail before any replay or regression JSON" in lifecycle_doc
    assert "list entries must also have `validated: true`" in lifecycle_doc
    assert "stored under the wrong kind bucket" in lifecycle_doc
    assert "verifies the reviewed artifact hash" in lifecycle_doc
    assert "verifies the source artifact and manifest hashes" in lifecycle_doc
    assert "--check" in lifecycle_doc
    assert "harness command" in lifecycle_doc
    assert "measured timing" in lifecycle_doc
    assert "timing fields" in lifecycle_doc
    assert "review artifact" in lifecycle_doc
    assert "regression artifact" in lifecycle_doc
    assert "learning export" in lifecycle_doc
    assert "JSONL SHA-256" in lifecycle_doc
    assert "verifies the JSONL content" in lifecycle_doc
    assert "not an actual model training run" in lifecycle_doc
    assert "HEAD SHA" in lifecycle_doc
    assert "diff" in lifecycle_doc
    assert "actual JSON files" in lifecycle_doc
    assert "validated: true" in lifecycle_doc
    assert "statuses, validation flags" in lifecycle_doc
    assert "wrong kind bucket" in lifecycle_doc
    assert "validated with" in lifecycle_doc
