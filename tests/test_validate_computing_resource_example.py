from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

from scripts.validate_computing_resource_example import ValidationSummary

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_computing_resource_example.py"
EXAMPLE_DIR = ROOT / "examples" / "computing-resource-workflow"


def run_validator(example_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(example_dir), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        output for output in (result.stdout.strip(), result.stderr.strip()) if output
    )


def load_json_object(path: Path) -> dict[str, object]:
    loaded = cast("object", json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    return cast("dict[str, object]", loaded)


def test_example_pack_validates_local_evidence_backed_report() -> None:
    result = run_validator(EXAMPLE_DIR)

    assert result.returncode == 0, result.stderr
    payload = ValidationSummary.model_validate_json(result.stdout)
    assert payload.status == "pass"
    assert payload.workflow_steps == 5
    assert payload.workflow_trace_steps == 5
    assert payload.report_sections == (
        "run_summary",
        "actual_local_evidence",
        "workflow_trace",
        "as_is",
        "to_be",
        "effects",
    )
    assert payload.local_execution.cpu_logical_cores > 0
    assert payload.local_execution.gpu_usage_claimed is False
    assert payload.local_execution.cost_claimed is False

    output_report = Path(payload.output_report)
    assert output_report.exists()
    assert "## Workflow Trace" in output_report.read_text(encoding="utf-8")


def test_validator_rejects_missing_required_request_field(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    request_path = scenario_dir / "inputs" / "resource-request.yaml"
    request_text = request_path.read_text(encoding="utf-8")
    updated_lines = [
        line for line in request_text.splitlines() if not line.startswith("request_id:")
    ]
    _ = request_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "request_id" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_validator_rejects_gpu_usage_claim_without_evidence(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    evidence_text = evidence_path.read_text(encoding="utf-8")
    _ = evidence_path.write_text(
        evidence_text.replace('"gpu_usage_claimed": false', '"gpu_usage_claimed": true'),
        encoding="utf-8",
    )

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "must not claim GPU usage" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_validator_rejects_cost_claim_without_evidence(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    evidence_text = evidence_path.read_text(encoding="utf-8")
    _ = evidence_path.write_text(
        evidence_text.replace('"cost_claimed": false', '"cost_claimed": true'),
        encoding="utf-8",
    )

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "must not claim cost" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_validator_rejects_missing_workflow_trace(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    evidence_payload = load_json_object(evidence_path)
    del evidence_payload["workflow_trace"]
    _ = evidence_path.write_text(json.dumps(evidence_payload), encoding="utf-8")

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "workflow_trace" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_validator_rejects_workflow_trace_that_disagrees_with_yaml(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    evidence_payload = load_json_object(evidence_path)
    workflow_trace_value = evidence_payload["workflow_trace"]
    assert isinstance(workflow_trace_value, list)
    workflow_trace = cast("list[object]", workflow_trace_value)
    first_trace = workflow_trace[0]
    assert isinstance(first_trace, dict)
    first_trace_payload = cast("dict[str, object]", first_trace)
    first_trace_payload["owner"] = "sample-owner"
    _ = evidence_path.write_text(json.dumps(evidence_payload), encoding="utf-8")

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "Workflow trace must match" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_validator_rejects_report_that_disagrees_with_local_evidence(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    report_path = scenario_dir / "outputs" / "resource-usage-report.md"
    report_text = report_path.read_text(encoding="utf-8")
    stale_report_text = report_text.replace(
        "## Effects / 도입 효과",
        "## Effects / 도입 효과\n\n- unsupported extra line",
        1,
    )
    _ = report_path.write_text(stale_report_text, encoding="utf-8")

    result = run_validator(scenario_dir)

    assert result.returncode != 0
    assert "generated output" in combined_output(result)
    assert "Traceback" not in combined_output(result)


def test_write_report_refreshes_local_evidence_and_regenerates_report(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "computing-resource-workflow"
    _ = shutil.copytree(EXAMPLE_DIR, scenario_dir)

    report_path = scenario_dir / "outputs" / "resource-usage-report.md"
    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    _ = report_path.write_text("# stale report\n", encoding="utf-8")
    _ = evidence_path.write_text('{"status": "pass"}\n', encoding="utf-8")

    result = run_validator(scenario_dir, "--write-report")

    assert result.returncode == 0, result.stderr
    payload = ValidationSummary.model_validate_json(result.stdout)
    report_text = report_path.read_text(encoding="utf-8")
    evidence_text = evidence_path.read_text(encoding="utf-8")

    assert payload.local_execution.cpu_logical_cores > 0
    assert "외부 GPU 사용 주장: 아니오" in report_text
    assert "비용 사용 주장: 아니오" in report_text
    assert "## Workflow Trace" in report_text
    assert "NVIDIA L40S 4장" not in report_text
    assert "708 USD" not in report_text
    assert '"cpu_logical_cores"' in evidence_text
    assert '"workflow_trace"' in evidence_text
