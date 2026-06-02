# Resource Usage Report

## Run Summary

- 요청 ID: local-omf-validation-2026-06-02
- 워크로드: computing-resource-workflow-report-generation
- 실행 명령: `uv run python scripts/validate_computing_resource_example.py examples/computing-resource-workflow --write-report`
- 출력 리포트: `examples/computing-resource-workflow/outputs/resource-usage-report.md`
- 검증 플랫폼: Darwin 25.6.0 arm64
- Python: 3.14.4
- 논리 CPU 코어: 10
- 메모리: 32.0 GiB
- nvidia-smi 사용 가능: 사용 불가
- 외부 GPU 사용 주장: 아니오
- 비용 사용 주장: 아니오

## Actual Local Evidence

- 현재 명령은 `uv run python scripts/validate_computing_resource_example.py examples/computing-resource-workflow --write-report` 계약으로 실행 evidence를 갱신했다.
- 현재 환경에서 감지한 논리 CPU 코어는 10개다.
- 현재 환경에서 감지한 메모리는 32.0 GiB다.
- `nvidia-smi` 명령은 사용 불가 상태다.
- GPU 사용량과 비용은 별도 evidence가 없으므로 주장하지 않는다.

## Workflow Trace

- request / requester / pass: Define local validation request - validated request local-omf-validation-2026-06-02 for workload computing-resource-workflow-report-generation
- approval / ops-manager / pass: Reject unsupported resource claims - rejected unsupported GPU usage and billing claims because no separate evidence artifact is present
- allocation / platform-engineer / pass: Capture local CPU and memory evidence - captured local runtime Darwin 25.6.0 arm64, Python 3.14.4, logical CPU cores 10, memory 32.0 GiB, nvidia-smi 사용 불가
- execution / job-runner / pass: Regenerate report from evidence - rendered report from local evidence to examples/computing-resource-workflow/outputs/resource-usage-report.md
- report / analyst / pass: Validate evidence-backed report - bound report validation to regenerated evidence-backed output

## As-Is

- 증거 없이 GPU 모델, GPU 수량, CPU 할당량, 비용을 쓰면 로컬 실행 결과처럼 오인된다.
- 그런 리포트는 실제 동작 입증이 아니라 fixture 기반 눈속임이다.

## To-Be

- 리포트는 현재 실행으로 갱신된 `evidence/local-execution.json`의 값만 사용한다.
- 외부 GPU 사용량이나 비용은 증거 파일이 없으면 출력하지 않는다.
- 리포트 파일이 evidence에서 재생성한 결과와 다르면 검증이 실패한다.

## Effects / 도입 효과

- 근거 없는 외부 GPU, 비용, CPU 할당 주장을 제거했다.
- 현재 검증 가능한 CPU 정보는 논리 CPU 코어 10개다.
- 현재 검증 가능한 메모리 정보는 32.0 GiB다.
- 현재 `nvidia-smi` 상태는 사용 불가다.
- 비용 사용량은 billing evidence가 없으므로 리포트에서 주장하지 않는다.
