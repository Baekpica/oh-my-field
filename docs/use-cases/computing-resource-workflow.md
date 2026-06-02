# 컴퓨팅 리소스 워크플로우 예제

## 매우 중요한 원칙

실제로 동작이 입증되지 않은 값은 리포트에 쓰지 않는다. GPU 모델, GPU 수량, CPU 할당량, 비용, 성능 개선, 완료 시간 같은 운영 수치는 실행 evidence나 외부 증빙 파일이 있을 때만 결과로 주장할 수 있다.

fixture, mock, 추정치, 보기 좋은 숫자를 실제 결과처럼 보여주는 예제는 출시 대상이 아니다. 그런 예제는 즉시 폐기하거나 harness를 고쳐야 한다.

## 목표

이 예제는 AI Agent가 리소스 사용 리포트를 만들 때, 현재 환경에서 실제로 확인한 값만 산출물에 남기도록 강제한다.

현재 구현은 다음을 수행한다.

- `inputs/resource-request.yaml`에서 리포트 생성 명령과 출력 파일 계약을 읽는다.
- `--write-report` 실행 시 현재 머신의 로컬 실행 evidence를 `evidence/local-execution.json`에 저장한다.
- `workflow/resource-workflow.yaml`의 5단계가 실제 `workflow_trace`로 evidence에 남았는지 검증한다.
- OS, Python, 논리 CPU 코어, 메모리, `nvidia-smi` availability처럼 현재 환경에서 확인 가능한 값만 리포트에 쓴다.
- GPU 사용량과 비용은 별도 evidence가 없으면 “주장하지 않음”으로 남긴다.
- 리포트가 evidence에서 재생성한 결과와 다르면 검증을 실패시킨다.

## 실제 실행 결과

현재 환경에서 다음 명령을 실행해 evidence와 report를 생성했다.

```bash
uv run python scripts/validate_computing_resource_example.py examples/computing-resource-workflow --write-report
```

생성된 `evidence/local-execution.json`은 다음 사실을 기록한다.

- 플랫폼: `Darwin 25.6.0 arm64`
- Python: `3.14.4`
- 논리 CPU 코어: `10`
- 메모리: `34359738368` bytes, report 표기 `32.0 GiB`
- `nvidia-smi`: 사용 불가
- 외부 GPU 사용 주장: `false`
- 비용 사용 주장: `false`
- workflow trace 단계 수: `5`

검증기는 같은 evidence에서 `outputs/resource-usage-report.md`를 재생성하고, 현재 파일과 정확히 일치하는지 확인한다.

## 입력

- `examples/computing-resource-workflow/inputs/resource-request.yaml`
  - 요청 ID, 팀, 요청자, 워크로드 이름, 실행 명령, 출력 리포트 경로를 포함한다.
- `examples/computing-resource-workflow/workflow/resource-workflow.yaml`
  - request -> approval -> allocation -> execution -> report 순서의 5단계 업무 절차를 정의한다.
  - validator는 이 YAML과 `evidence/local-execution.json`의 `workflow_trace`가 일치하는지 확인한다.

## Evidence

- `examples/computing-resource-workflow/evidence/local-execution.json`
  - validator가 현재 환경에서 생성한 evidence다.
  - 사람이 손으로 만든 GPU/비용 fixture가 아니다.
  - workflow YAML의 각 단계가 어떤 owner와 detail로 실행 trace에 남았는지 포함한다.

## Outputs

- `examples/computing-resource-workflow/outputs/resource-usage-report.md`
  - `Run Summary`, `Actual Local Evidence`, `Workflow Trace`, `As-Is`, `To-Be`, `Effects / 도입 효과` 섹션을 포함한다.
  - 리포트는 `local-execution.json`에 없는 GPU 사용량이나 비용을 주장하지 않는다.

## As-Is

- Agent가 리포트를 그럴듯하게 만들기 위해 GPU 모델, GPU 수량, CPU 할당량, 비용을 fixture로 넣을 수 있었다.
- 이런 방식은 현재 로컬 환경에서 실행했는데도 외부 NVIDIA GPU와 billing spend를 사용한 것처럼 보이게 만든다.
- 실제 검증을 통해 출시하려는 서비스 기준에서는 눈속임이므로 폐기 대상이다.

## To-Be

- Agent는 현재 실행으로 갱신된 `local-execution.json`만 근거로 리포트를 작성한다.
- 현재 환경에서 검증 가능한 CPU, 메모리, OS, Python, `nvidia-smi` availability만 출력한다.
- workflow 단계는 YAML에 적힌 이름만 확인하는 것이 아니라, 현재 evidence의 `workflow_trace`와 일치해야 한다.
- GPU 사용량이나 비용은 실제 evidence artifact가 추가되기 전까지 주장하지 않는다.
- 문서와 예제는 기능 구현과 검증이 끝난 뒤, 생성된 evidence와 report를 기준으로 작성한다.

## Harness / QA

검증기는 다음 조건을 확인한다.

- 필수 파일이 모두 존재한다.
- 리소스 요청 YAML의 필수 필드가 모두 존재하고 추가 필드가 없다.
- 워크플로우 단계가 request, approval, allocation, execution, report 순서와 정확히 일치한다.
- `local-execution.json`의 `workflow_trace`가 워크플로우 YAML과 현재 evidence에서 재생성한 trace와 정확히 일치한다.
- `local-execution.json`의 command가 요청 YAML의 command와 일치한다.
- 논리 CPU 코어 값이 양수다.
- GPU 사용량 주장이 있으면 실패한다.
- 비용 사용량 주장이 있으면 실패한다.
- 리포트 파일은 현재 evidence에서 생성되는 결과와 정확히 일치한다.

## 플랫폼 / 런타임 효과

- Python 3.13 이상과 `uv`가 있으면 macOS, Linux, CI에서 같은 검증 흐름을 실행할 수 있다.
- 환경별 값은 `--write-report` 실행 시 새 evidence로 갱신된다.
- 하드웨어나 비용처럼 환경 의존적인 주장은 evidence가 없으면 출력되지 않는다.
- 출시 문서는 “보여주기 좋은 예시”가 아니라 재현 가능한 command output과 artifact를 기준으로 작성된다.

## 검증 명령

```bash
uv sync --dev
uv run python scripts/validate_computing_resource_example.py examples/computing-resource-workflow --write-report
uv run python scripts/validate_computing_resource_example.py examples/computing-resource-workflow
uv run pytest tests/test_validate_computing_resource_example.py tests/test_docs_computing_resource_use_case.py -q
```
