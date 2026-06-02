from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, ClassVar, Final, Literal, final, override

import typer
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

type YamlScalar = str | int | float | bool | None
type YamlKey = YamlScalar | tuple["YamlKey", ...]
type YamlValue = YamlScalar | list["YamlValue"] | dict["YamlKey", "YamlValue"]


class ResourceRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    team: str
    requester: str
    workload_name: str
    command: str
    output_report: str


class WorkflowStep(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    owner: str


class WorkflowDefinition(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[WorkflowStep, ...]


class WorkflowStepTrace(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    owner: str
    status: Literal["pass"]
    detail: str


class LocalExecutionEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    status: Literal["pass"]
    job_id: str
    command: str
    platform_system: str
    platform_release: str
    machine: str
    python_version: str
    cpu_logical_cores: int
    memory_bytes: int | None
    nvidia_smi_available: bool
    gpu_usage_claimed: bool
    cost_claimed: bool
    workflow_trace: tuple[WorkflowStepTrace, ...]


class LocalExecutionSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    platform: str
    cpu_logical_cores: int
    memory_bytes: int | None
    nvidia_smi_available: bool
    gpu_usage_claimed: bool
    cost_claimed: bool


class ValidationSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["pass"]
    workflow_steps: int
    workflow_trace_steps: int
    report_sections: tuple[str, ...]
    local_execution: LocalExecutionSummary
    output_report: str


@final
@dataclass(frozen=True, slots=True)
class ExamplePackError(Exception):
    message: str

    @classmethod
    def missing_file(cls, relative_path: Path) -> ExamplePackError:
        return cls(f"Missing required file: {relative_path}")

    @classmethod
    def invalid_resource_request(
        cls, file_name: str, error: ValidationError | TypeError
    ) -> ExamplePackError:
        detail = f": {error}" if str(error) else ""
        return cls(f"Invalid resource request in {file_name}{detail}")

    @classmethod
    def invalid_workflow_definition(
        cls, file_name: str, error: ValidationError | TypeError
    ) -> ExamplePackError:
        detail = f": {error}" if str(error) else ""
        return cls(f"Invalid workflow definition in {file_name}{detail}")

    @classmethod
    def invalid_local_execution(cls, file_name: str, error: ValidationError) -> ExamplePackError:
        return cls(f"Invalid local execution evidence in {file_name}: {error}")

    @classmethod
    def command_mismatch(cls, expected: str, actual: str) -> ExamplePackError:
        return cls(f"Local execution command mismatch: expected {expected!r}, got {actual!r}")

    @classmethod
    def missing_cpu_evidence(cls) -> ExamplePackError:
        return cls("Local execution evidence must include a positive cpu_logical_cores value")

    @classmethod
    def unsupported_gpu_usage_claim(cls) -> ExamplePackError:
        return cls("Local report must not claim GPU usage without a GPU usage evidence artifact")

    @classmethod
    def unsupported_cost_claim(cls) -> ExamplePackError:
        return cls("Local report must not claim cost without a billing evidence artifact")

    @classmethod
    def report_does_not_match_generated_output(cls) -> ExamplePackError:
        return cls("Invalid example contract: report must match generated output")

    @classmethod
    def invalid_workflow_steps(cls) -> ExamplePackError:
        return cls(
            "Workflow steps must be exactly request, approval, allocation, execution, report."
        )

    @classmethod
    def invalid_workflow_trace(cls) -> ExamplePackError:
        return cls(
            "Workflow trace must match workflow/resource-workflow.yaml and current local evidence."
        )

    @classmethod
    def missing_report_section(cls, section_heading: str) -> ExamplePackError:
        return cls(f"Missing report section: {section_heading}")

    @classmethod
    def missing_report_detail(cls, detail: str) -> ExamplePackError:
        return cls(f"Invalid example contract: report must contain: {detail}")

    @override
    def __str__(self) -> str:
        return self.message


REQUIRED_FILES: Final[tuple[Path, ...]] = (
    Path("README.md"),
    Path("inputs/resource-request.yaml"),
    Path("workflow/resource-workflow.yaml"),
    Path("outputs/resource-usage-report.md"),
    Path("evidence/local-execution.json"),
)
EXPECTED_STEP_IDS: Final[tuple[str, ...]] = (
    "request",
    "approval",
    "allocation",
    "execution",
    "report",
)
REPORT_SECTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("run_summary", "## Run Summary"),
    ("actual_local_evidence", "## Actual Local Evidence"),
    ("workflow_trace", "## Workflow Trace"),
    ("as_is", "## As-Is"),
    ("to_be", "## To-Be"),
    ("effects", "## Effects / 도입 효과"),
)

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def ensure_required_files(example_dir: Path) -> None:
    for relative_path in REQUIRED_FILES:
        artifact_path = example_dir / relative_path
        if not artifact_path.exists():
            raise ExamplePackError.missing_file(relative_path)


def load_yaml_mapping(path: Path) -> dict[str, YamlValue]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError

    payload: dict[str, YamlValue] = {}
    for key, value in loaded.items():
        if not isinstance(key, str):
            raise TypeError
        payload[key] = value
    return payload


def parse_resource_request(path: Path) -> ResourceRequest:
    try:
        return ResourceRequest.model_validate(load_yaml_mapping(path))
    except (ValidationError, TypeError) as error:
        raise ExamplePackError.invalid_resource_request(path.name, error) from error


def parse_workflow_definition(path: Path) -> WorkflowDefinition:
    try:
        return WorkflowDefinition.model_validate(load_yaml_mapping(path))
    except (ValidationError, TypeError) as error:
        raise ExamplePackError.invalid_workflow_definition(path.name, error) from error


def parse_local_execution(path: Path) -> LocalExecutionEvidence:
    try:
        return LocalExecutionEvidence.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise ExamplePackError.invalid_local_execution(path.name, error) from error


def detect_memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    if pages <= 0 or page_size <= 0:
        return None
    return pages * page_size


def build_workflow_trace(
    request: ResourceRequest,
    workflow: WorkflowDefinition,
    evidence: LocalExecutionEvidence,
) -> tuple[WorkflowStepTrace, ...]:
    _ = validate_workflow_steps(workflow)
    platform_label = (
        f"{evidence.platform_system} {evidence.platform_release} {evidence.machine}"
    )
    details = {
        "request": (
            f"validated request {request.request_id} for workload "
            f"{request.workload_name}"
        ),
        "approval": (
            "rejected unsupported GPU usage and billing claims because no "
            "separate evidence artifact is present"
        ),
        "allocation": (
            f"captured local runtime {platform_label}, Python "
            f"{evidence.python_version}, logical CPU cores "
            f"{evidence.cpu_logical_cores}, memory {format_memory(evidence.memory_bytes)}, "
            f"nvidia-smi {format_available_ko(evidence.nvidia_smi_available)}"
        ),
        "execution": f"rendered report from local evidence to {request.output_report}",
        "report": "bound report validation to regenerated evidence-backed output",
    }
    return tuple(
        (
            WorkflowStepTrace(
                id=step.id,
                name=step.name,
                owner=step.owner,
                status="pass",
                detail=details[step.id],
            )
        )
        for step in workflow.steps
    )


def collect_local_execution(
    request: ResourceRequest, workflow: WorkflowDefinition
) -> LocalExecutionEvidence:
    cpu_count = os.cpu_count() or 0
    evidence = LocalExecutionEvidence(
        status="pass",
        job_id="local-current-environment",
        command=request.command,
        platform_system=platform.system(),
        platform_release=platform.release(),
        machine=platform.machine(),
        python_version=sys.version.split()[0],
        cpu_logical_cores=cpu_count,
        memory_bytes=detect_memory_bytes(),
        nvidia_smi_available=shutil.which("nvidia-smi") is not None,
        gpu_usage_claimed=False,
        cost_claimed=False,
        workflow_trace=(),
    )
    return evidence.model_copy(
        update={"workflow_trace": build_workflow_trace(request, workflow, evidence)}
    )


def validate_workflow_steps(workflow: WorkflowDefinition) -> int:
    actual_step_ids = tuple(step.id for step in workflow.steps)
    if actual_step_ids != EXPECTED_STEP_IDS:
        raise ExamplePackError.invalid_workflow_steps()
    return len(actual_step_ids)


def format_bool_ko(value: bool) -> str:
    return "예" if value else "아니오"


def format_available_ko(value: bool) -> str:
    return "사용 가능" if value else "사용 불가"


def format_memory(memory_bytes: int | None) -> str:
    if memory_bytes is None:
        return "감지 불가"
    gibibytes = memory_bytes / (1024**3)
    return f"{gibibytes:.1f} GiB"


def validate_local_execution_contract(
    request: ResourceRequest, evidence: LocalExecutionEvidence
) -> tuple[str, ...]:
    if evidence.command != request.command:
        raise ExamplePackError.command_mismatch(request.command, evidence.command)
    if evidence.cpu_logical_cores <= 0:
        raise ExamplePackError.missing_cpu_evidence()
    if evidence.gpu_usage_claimed:
        raise ExamplePackError.unsupported_gpu_usage_claim()
    if evidence.cost_claimed:
        raise ExamplePackError.unsupported_cost_claim()

    platform_label = (
        f"{evidence.platform_system} {evidence.platform_release} {evidence.machine}"
    )
    return (
        f"- 요청 ID: {request.request_id}",
        f"- 워크로드: {request.workload_name}",
        f"- 실행 명령: `{request.command}`",
        f"- 출력 리포트: `{request.output_report}`",
        f"- 검증 플랫폼: {platform_label}",
        f"- Python: {evidence.python_version}",
        f"- 논리 CPU 코어: {evidence.cpu_logical_cores}",
        f"- 메모리: {format_memory(evidence.memory_bytes)}",
        f"- nvidia-smi 사용 가능: {format_available_ko(evidence.nvidia_smi_available)}",
        f"- 외부 GPU 사용 주장: {format_bool_ko(evidence.gpu_usage_claimed)}",
        f"- 비용 사용 주장: {format_bool_ko(evidence.cost_claimed)}",
    )


def validate_workflow_trace(
    request: ResourceRequest,
    workflow: WorkflowDefinition,
    evidence: LocalExecutionEvidence,
) -> int:
    expected_trace = build_workflow_trace(request, workflow, evidence)
    if evidence.workflow_trace != expected_trace:
        raise ExamplePackError.invalid_workflow_trace()
    return len(evidence.workflow_trace)


def format_bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_resource_usage_report(
    request: ResourceRequest,
    evidence: LocalExecutionEvidence,
) -> str:
    summary_lines = validate_local_execution_contract(request, evidence)
    actual_evidence_lines = (
        f"현재 명령은 `{request.command}` 계약으로 실행 evidence를 갱신했다.",
        f"현재 환경에서 감지한 논리 CPU 코어는 {evidence.cpu_logical_cores}개다.",
        f"현재 환경에서 감지한 메모리는 {format_memory(evidence.memory_bytes)}다.",
        f"`nvidia-smi` 명령은 {format_available_ko(evidence.nvidia_smi_available)} 상태다.",
        "GPU 사용량과 비용은 별도 evidence가 없으므로 주장하지 않는다.",
    )
    workflow_trace_lines = tuple(
        (
            f"{trace.id} / {trace.owner} / {trace.status}: "
            f"{trace.name} - {trace.detail}"
        )
        for trace in evidence.workflow_trace
    )
    as_is_lines = (
        "증거 없이 GPU 모델, GPU 수량, CPU 할당량, 비용을 쓰면 로컬 실행 결과처럼 오인된다.",
        "그런 리포트는 실제 동작 입증이 아니라 fixture 기반 눈속임이다.",
    )
    to_be_lines = (
        "리포트는 현재 실행으로 갱신된 `evidence/local-execution.json`의 값만 사용한다.",
        "외부 GPU 사용량이나 비용은 증거 파일이 없으면 출력하지 않는다.",
        "리포트 파일이 evidence에서 재생성한 결과와 다르면 검증이 실패한다.",
    )
    effect_lines = (
        "근거 없는 외부 GPU, 비용, CPU 할당 주장을 제거했다.",
        f"현재 검증 가능한 CPU 정보는 논리 CPU 코어 {evidence.cpu_logical_cores}개다.",
        f"현재 검증 가능한 메모리 정보는 {format_memory(evidence.memory_bytes)}다.",
        f"현재 `nvidia-smi` 상태는 {format_available_ko(evidence.nvidia_smi_available)}다.",
        "비용 사용량은 billing evidence가 없으므로 리포트에서 주장하지 않는다.",
    )

    return "\n".join(
        (
            "# Resource Usage Report",
            "",
            "## Run Summary",
            "",
            "\n".join(summary_lines),
            "",
            "## Actual Local Evidence",
            "",
            format_bullets(actual_evidence_lines),
            "",
            "## Workflow Trace",
            "",
            format_bullets(workflow_trace_lines),
            "",
            "## As-Is",
            "",
            format_bullets(as_is_lines),
            "",
            "## To-Be",
            "",
            format_bullets(to_be_lines),
            "",
            "## Effects / 도입 효과",
            "",
            format_bullets(effect_lines),
            "",
        )
    )


def write_resource_usage_report(example_dir: Path) -> Path:
    scenario_dir = example_dir.resolve()
    request = parse_resource_request(scenario_dir / "inputs" / "resource-request.yaml")
    workflow = parse_workflow_definition(scenario_dir / "workflow" / "resource-workflow.yaml")
    evidence = collect_local_execution(request, workflow)
    evidence_path = scenario_dir / "evidence" / "local-execution.json"
    _ = evidence_path.write_text(evidence.model_dump_json(indent=2) + "\n", encoding="utf-8")

    report_path = scenario_dir / "outputs" / "resource-usage-report.md"
    _ = report_path.write_text(
        render_resource_usage_report(request, evidence), encoding="utf-8"
    )
    return report_path


def validate_report_sections(path: Path, required_details: tuple[str, ...]) -> tuple[str, ...]:
    report_text = path.read_text(encoding="utf-8")
    report_sections: list[str] = []
    for section_key, section_heading in REPORT_SECTIONS:
        if section_heading not in report_text:
            raise ExamplePackError.missing_report_section(section_heading)
        report_sections.append(section_key)

    for detail in required_details:
        if detail not in report_text:
            raise ExamplePackError.missing_report_detail(detail)

    return tuple(report_sections)


def validate_example_pack(example_dir: Path) -> ValidationSummary:
    scenario_dir = example_dir.resolve()
    ensure_required_files(scenario_dir)

    request = parse_resource_request(scenario_dir / "inputs" / "resource-request.yaml")
    workflow = parse_workflow_definition(scenario_dir / "workflow" / "resource-workflow.yaml")
    workflow_steps = validate_workflow_steps(workflow)
    evidence = parse_local_execution(scenario_dir / "evidence" / "local-execution.json")
    required_report_details = validate_local_execution_contract(request, evidence)
    workflow_trace_steps = validate_workflow_trace(request, workflow, evidence)
    expected_report = render_resource_usage_report(request, evidence)
    report_path = scenario_dir / "outputs" / "resource-usage-report.md"
    if report_path.read_text(encoding="utf-8") != expected_report:
        raise ExamplePackError.report_does_not_match_generated_output()

    report_sections = validate_report_sections(report_path, required_report_details)
    return ValidationSummary(
        status="pass",
        workflow_steps=workflow_steps,
        workflow_trace_steps=workflow_trace_steps,
        report_sections=report_sections,
        local_execution=LocalExecutionSummary(
            platform=f"{evidence.platform_system} {evidence.platform_release} {evidence.machine}",
            cpu_logical_cores=evidence.cpu_logical_cores,
            memory_bytes=evidence.memory_bytes,
            nvidia_smi_available=evidence.nvidia_smi_available,
            gpu_usage_claimed=evidence.gpu_usage_claimed,
            cost_claimed=evidence.cost_claimed,
        ),
        output_report=str((scenario_dir / "outputs" / "resource-usage-report.md").resolve()),
    )


@app.command()
def validate(
    example_dir: Path,
    write_report: Annotated[
        bool,
        typer.Option(
            "--write-report",
            help="Refresh local execution evidence and regenerate the report before validating.",
        ),
    ] = False,
) -> None:
    try:
        if write_report:
            _ = write_resource_usage_report(example_dir)
        summary = validate_example_pack(example_dir)
    except ExamplePackError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    typer.echo(summary.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
