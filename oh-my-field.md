# Product Vision

- oh-my-field는 에이전트가 수행한 일회성 작업을 조직과 개인의 반복 가능한 업무 자산으로 전환하는 Field-oriented Agent Capability Platform 지향
- 사용자의 현장 업무 맥락, 암묵지, 시행착오, 검증 기준을 에이전트가 재사용 가능한 형태로 학습·축적·실행할 수 있도록 지원
- 단순 프롬프트 관리 도구가 아닌, 프롬프트·컨텍스트·실행 환경·검증 하네스·증거 수집·학습 후보 export까지 현재 구현하고, 실제 모델 학습은 후속 검증 대상으로 분리하는 agent workflow operating layer 지향
- 프론티어 모델, 로컬 모델, 폐쇄망 모델, 사내 특화 모델 등 런타임이 변경되어도 사용자의 업무 기준과 검증 가능한 실행 품질 유지
- “AI가 한 번 잘한 일”을 “언제든 다시 잘할 수 있는 capability”로 만드는 것에 집중

# Core Concept

## Field

- 사용자가 실제로 업무를 수행하는 도메인 환경
- 예: 코드베이스, 인프라 환경, 사내 운영 프로세스, 데이터 파이프라인, 고객 지원 절차, 보고서 작성 체계 등
- 단순 지식 문서가 아닌, 실행 가능한 업무 맥락과 판단 기준의 집합

## Capability

- 특정 업무를 에이전트가 반복적으로 수행할 수 있도록 패키징된 능력 단위
- 프롬프트, 컨텍스트, 입력 스키마, 실행 절차, 도구 사용 방식, 검증 하네스, 실패 대응 전략, 결과물 기준 포함
- 모델이 바뀌어도 재현 가능해야 하며, 실패 시 개선 가능한 구조 필요

## Evidence

- 에이전트가 업무를 수행하는 과정에서 생성·수집되는 판단 근거
- 예: 실행 로그, 커맨드 히스토리, 코드 diff, 테스트 결과, 사용자 피드백, 실패 케이스, 재시도 이력, 산출물 품질 평가 등
- 향후 capability 개선, 프롬프트 최적화, 하네스 보강, eval set 구성, fine-tuning 후보 검토의 근거로 활용
- 매우 중요: 실제로 실행·검증된 evidence가 없는 수치, 비용, 성능, 리소스 사용량, 개선 효과는 결과물이나 문서에 쓰지 않는다.
- fixture, mock, 추정치, 보기 좋은 숫자를 실제 동작 결과처럼 제시하는 기능은 출시 대상이 아니라 폐기 또는 하네스 수정 대상이다.

## Harness

- 에이전트 결과물을 검증하기 위한 테스트·평가·제약 조건의 집합
- 코드 작업의 경우 unit test, integration test, lint, type check, benchmark, smoke test 포함
- 문서/운영 업무의 경우 체크리스트, JSON schema, rubric, approval rule, human review 기준 포함
- capability가 실제 업무 기준을 만족하는지 확인하는 품질 게이트 역할 수행

## Runtime

- 에이전트가 실행되는 모델·도구·환경 계층
- Claude Code, Codex, OpenAI API, Anthropic API, 로컬 LLM, 사내 모델, MCP tool, shell, browser, DB, GitHub, Slack 등 포함
- omf는 특정 런타임에 종속되지 않고, capability가 다양한 실행 환경에서 재현될 수 있도록 추상화 계층 제공

# Target Users

## AI Engineer / Agent Engineer

- 특정 업무 도메인에 에이전트를 피팅하고, 반복 가능한 workflow와 evaluation harness를 구성하려는 사용자
- 에이전트 실패 로그와 사용자 개입을 바탕으로 capability를 개선하려는 사용자

## Field Domain Expert

- AI 모델 자체를 개발하지 않더라도, 자신의 업무 지식과 판단 기준을 agent workflow에 반영하고자 하는 사용자
- 기존 업무의 암묵지를 명시적 절차와 검증 기준으로 전환하려는 사용자

## DevOps / Infra / Platform Engineer

- 폐쇄망, 로컬 모델, 제한된 API 환경 등에서 agent workflow를 안정적으로 운영하고자 하는 사용자
- 실행 로그, 권한, 재현성, 감사 가능성을 중요하게 보는 사용자

## Small Team / Startup Operator

- 프론티어 모델을 활용해 빠르게 업무 자동화를 시작했으나, 작업 결과가 누적되지 않고 매번 새로 지시해야 하는 문제를 겪는 사용자
- 비용 효율성과 재사용성을 높이기 위해 agent capability library를 구축하려는 팀

# Product Goals

## 반복 업무의 capability화

- 사용자가 반복적으로 수행하는 프롬프트 기반 작업을 재사용 가능한 capability로 승격
- 단순 prompt template 저장이 아닌, 실행 절차·검증 기준·실패 복구 전략까지 포함한 패키지화

## 실패한 agent 작업의 자산화

- 에이전트 실패, 사용자 수정, 재시도, 로그, 히스토리를 evidence로 수집
- 실패를 단발성 오류로 소모하지 않고, 다음 실행의 품질 개선 재료로 전환

## 장시간 agent workflow 지원

- /goals, /ulw 등 장시간 작업 루프를 통해 복잡한 목표를 여러 단계로 분해·실행·검증·수정
- 단일 프롬프트-응답 구조를 넘어, 상태를 유지하는 multi-step workflow 지원

## 모델/런타임 독립성 확보

- 동일 capability를 다양한 모델과 실행 환경에서 재사용 가능하게 구성
- 고성능 프론티어 모델에서 생성한 workflow를 저성능 로컬 모델 또는 제한된 사내 모델 환경에서도 활용 가능하도록 압축·보강

## 검증 가능한 업무 자동화

- 결과물 생성 자체보다 결과물의 검증 가능성, 재현성, 감사 가능성에 집중
- “에이전트가 답했다”가 아니라 “검증 기준을 통과했다”를 최종 완료 조건으로 정의

# Non-Goals

- 모든 업무를 완전 자동화하는 범용 AGI 시스템 지향 아님
- 단순 프롬프트 저장소 또는 prompt marketplace 지향 아님
- 특정 LLM provider 또는 특정 coding agent에 종속되는 wrapper 지향 아님
- 사람의 판단을 완전히 제거하는 autonomous-only 시스템 지향 아님
- 검증 불가능한 결과물을 무조건 신뢰하는 black-box automation 지향 아님

# Representative Use Cases

## Coding Agent Workflow 고도화

- 사용자가 기존에 반복하던 코드 수정, 테스트, 리팩토링, 문서화 작업을 capability로 전환
- 실패한 agent run에서 발생한 로그, diff, test failure, 사용자 수정사항을 evidence로 수집
- 이후 유사 작업 수행 시 기존 evidence를 바탕으로 context와 harness 자동 주입

## Infra Operation Runbook Agent화

- 장애 대응, 배포 점검, 로그 분석, 리소스 확인 절차를 agent workflow로 구성
- 명령어 실행, 결과 파싱, 이상 징후 판단, 보고서 생성까지 단계화
- human approval이 필요한 지점과 자동 실행 가능한 지점 분리

## Computing Resource Workflow Agent화

- 현재 실행 환경에서 감지한 OS, Python, 논리 CPU 코어, 메모리, `nvidia-smi` availability를 evidence로 저장
- GPU 사용량이나 비용 evidence가 없으면 리포트에서 해당 사용량을 주장하지 않도록 validator로 차단
- 입력 계약, local execution evidence, validator, output report를 묶어 보고서를 재생성 가능하게 구성

## Domain Report Generation

- 반복적으로 작성되는 업무 보고서, 리서치 요약, 회의록, 운영 리포트를 capability로 구성
- 단순 문체 모방이 아니라, 조직별 판단 기준·용어·금지 표현·근거 수집 규칙을 포함
- 결과물에 대한 human feedback을 누적하여 rubric과 prompt 개선

## Offline / Local Agent Optimization

- 폐쇄망 또는 로컬 모델 환경에서 부족한 모델 성능을 보완하기 위해, 프론티어 모델에서 생성한 고품질 workflow를 압축·이식
- 실행 예시, 실패 예시, tool-use pattern, 검증 기준을 함께 제공하여 작은 모델의 업무 수행 능력 보강

# Core Workflow

## 1. Observe

- 사용자의 실제 agent 작업 로그, 프롬프트, 스크립트, 커맨드, 실행 결과, 실패 이력 수집
- 단순 성공 산출물뿐 아니라 중간 사고 과정에 해당하는 실행 흔적과 환경 정보 수집

## 2. Structure

- 수집된 작업을 목표, 입력, 절차, 도구, 산출물, 검증 기준, 실패 조건으로 구조화
- 일회성 agent interaction을 workflow graph로 변환

## 3. Harness

- capability의 성공 여부를 판단할 수 있는 평가 기준 구성
- 자동 테스트, schema validation, lint, benchmark, checklist, human approval gate 등 설정

## 4. Execute

- LangGraph 기반 node workflow 또는 유사한 graph runtime을 통해 작업 실행
- 각 node는 독립적인 책임을 가지며, 상태와 evidence를 명시적으로 전달

## 5. Evaluate

- 실행 결과를 harness 기준으로 검증
- 실패 시 원인 분류, 재시도 전략 수립, context 보강, prompt 수정, tool call 재구성

## 6. Promote

- 검증을 통과한 workflow를 reusable capability로 승격
- capability registry에 저장하고, 이후 유사 작업에서 검색·재사용 가능하게 구성

## 7. Learn

- 현재 구현된 범위는 검증된 omf artifact를 `omf learn`으로 local JSONL learning candidate set과 manifest로 export하는 것
- prompt optimization, context packing, retrieval policy 개선, eval set 구성, fine-tuning dataset 후보 검토는 export된 evidence를 근거로 별도 검증해야 함
- 실제 model training, preference 학습, prompt patch 자동 적용은 아직 출시 기능으로 주장하지 않음

# LangGraph-based Workflow Design

- omf는 장시간·다단계 agent 작업을 견고하게 처리하기 위해 LangGraph 기반 workflow 구성을 고려
- 각 작업은 단일 프롬프트가 아니라 상태를 가진 graph로 표현
- node는 명확한 책임 단위로 분리하며, edge는 성공·실패·보류·사용자 승인 등 상태 전이를 표현

## 주요 node 예시

### Goal Parser Node

- 사용자 요청을 목표, 제약 조건, 완료 기준, 예상 산출물로 분해

### Context Collector Node

- 코드베이스, 문서, 로그, 이전 evidence, 사용자 선호, 환경 정보를 수집

### Plan Builder Node

- 목표 달성을 위한 단계별 실행 계획 생성

### Tool Execution Node

- shell, git, browser, DB, API, MCP tool 등 실제 도구 실행

### Harness Runner Node

- 테스트, lint, type check, schema validation, benchmark, rubric 평가 수행

### Evidence Collector Node

- 실행 로그, 결과물, 실패 원인, 사용자 개입, 재시도 이력 저장

### Reflection Node

- 실패 또는 품질 미달 결과에 대해 원인 분석 및 수정 방향 도출

### Human Review Node

- 사용자 승인, 수정 요청, 중단, 재실행 여부 판단

### Capability Packager Node

- 성공한 workflow를 capability manifest로 변환

### Learning Export Node

- 검증된 evidence/replay/eval/review/regression artifact를 JSONL learning candidate로 export
- 현재 MVP 범위에서는 local JSONL export까지만 출시 기능이며, 실제 model training/fine-tuning은 구현된 기능으로 주장하지 않음

# Command Interface

## `omf capture`

- 실제 shell command를 local shell invocation으로 실행하고 exit code, stdout, stderr, runtime, artifact SHA-256을 evidence JSON으로 저장
- redirection 같은 shell syntax는 실제 실행 결과로 검증하며, 실행에 사용한 shell args도 command result에 기록
- `--check`로 지정한 harness command도 같은 방식으로 실제 실행하고, 하나라도 실패하면 evidence를 fail로 기록
- Git repository 안에서 실행하면 repository root, HEAD, branch, changed files, diff SHA-256을 evidence로 저장
- 실패한 작업도 evidence로 저장하지만, 실패 evidence는 capability로 승격할 수 없음
- 향후 capability 후보로 승격하기 위한 raw material 확보

## `omf promote`

- `omf capture`로 생성된 passing evidence만 capability manifest로 승격
- evidence에 기록된 command, cwd, artifact hash, harness command를 manifest에 고정
- source evidence SHA-256을 함께 저장해 원본 evidence 변조를 `omf inspect`에서 잡을 수 있게 함

## `omf replay`

- capability manifest의 command를 실제 재실행
- 실행 전에 capability manifest의 source evidence SHA-256과 promoted contract가 `omf inspect` 기준으로 유효해야 함
- exit code, artifact hash, harness command 통과 여부를 promote 당시 계약과 비교
- replay evidence path/SHA-256과 capability manifest path/SHA-256을 replay artifact에 저장
- `omf inspect`가 replay evidence와 manifest를 다시 읽어 checks, timing, status를 재계산해야 유효한 replay artifact로 인정

## `omf eval`

- capability replay를 지정 횟수만큼 실제 실행
- eval 입력 manifest는 먼저 `omf inspect` 기준의 capability 검증을 통과해야 하며, invalid manifest는 replay/eval artifact를 만들기 전에 실패
- pass count, pass rate, replay result 경로, 실제 command/harness timing summary를 eval artifact로 저장
- `omf inspect`가 embedded replay result들을 재검증하고 pass count/rate/status/timing을 재계산해야 유효한 eval artifact로 인정
- 비용은 별도 billing evidence가 없으면 측정값처럼 기록하지 않음

## `omf list`

- 로컬 store의 evidence, capability manifest, replay, eval, review, regression, learning JSON artifact를 실제 파일 기준으로 조회
- 각 entry는 `omf inspect` 검증을 통과해야 하며 status와 validated flag를 포함
- 깨진 JSON, schema mismatch, hash mismatch, 잘못된 store bucket이 있으면 list는 실패
- 존재하지 않는 registry 항목을 꾸며내지 않고, `.omf` 아래에 있는 검증된 파일만 인덱싱

## `omf inspect`

- evidence, capability, replay, eval, review, regression, learning JSON artifact를 schema별로 검증하고 요약 출력
- evidence artifact는 command/harness status를 재계산하고 기록된 artifact 파일의 존재, SHA-256, size를 재검증
- capability artifact는 source evidence 파일 존재, SHA-256, passing status, promoted command/artifact/check 계약 일치를 재검증
- replay artifact는 manifest/evidence 파일 존재, SHA-256, command/artifact/check/timing/status 일치를 재검증
- eval artifact는 embedded replay result, pass count/rate/status/timing 일치를 재검증
- review artifact는 reviewed artifact 파일 존재, SHA-256, type/status 일치를 재검증
- regression artifact는 source artifact와 capability manifest 파일 존재, SHA-256, type/status, capability name, embedded replay status 일치를 재검증
- learning artifact는 manifest만 보지 않고 JSONL 파일 존재, SHA-256, row schema, row count, manifest item 일치 여부와 source artifact path/SHA-256/type/status까지 재검증
- schema가 지원되지 않거나 깨진 JSON이면 실패

## `omf review`

- 검증 가능한 omf JSON artifact에 대해 reviewer, decision, note를 실제 review JSON artifact로 저장
- reviewed artifact의 경로, SHA-256, artifact type, status를 함께 저장해 어떤 산출물에 대한 판단인지 추적
- `omf inspect`가 reviewed artifact hash와 type/status를 다시 확인해야 유효한 review artifact로 인정
- 지원 decision은 approve, reject, revise, add_context, change_goal, change_constraint, mark_reusable, mark_unsafe, create_regression_case로 제한
- 실제 approval gate나 workflow 중단/재개 orchestration은 아직 출시 기능으로 주장하지 않음

## `omf regress`

- capability manifest와 source omf artifact를 받아 regression case JSON artifact를 생성
- source artifact와 capability manifest가 먼저 `omf inspect` 검증을 통과해야 하며, invalid manifest는 regression/replay artifact를 만들기 전에 실패
- source artifact와 manifest의 경로, SHA-256, type/status, reason을 함께 저장
- case 생성 시 capability replay를 실제 실행하고 replay result를 regression artifact에 포함
- `omf inspect`가 source artifact와 capability manifest hash를 다시 확인해야 유효한 regression artifact로 인정
- 단순 label이나 샘플 eval set이 아니라, 생성 시점에 재실행된 결과를 근거로 함

## `omf learn`

- 검증 가능한 omf JSON artifact를 받아 local JSONL learning candidate set과 manifest를 생성
- source artifact의 경로, SHA-256, type, status를 item마다 저장
- manifest에는 JSONL 경로, JSONL SHA-256, item count, purpose를 저장
- `omf inspect`가 JSONL 파일을 다시 읽어 hash와 row 내용을 검증할 수 있어야 learning export로 인정
- 지원 purpose는 prompt_improvement, eval_set, fine_tuning_candidate로 제한
- 실제 model training, dataset upload, fine-tuning job 실행은 아직 출시 기능으로 주장하지 않음

## `omf search`

- 로컬 store의 evidence, capability, replay, eval, review, regression, learning JSON artifact 파일을 실제로 읽고 text query로 검색
- 검색 결과로 반환되는 artifact는 `omf inspect` 검증을 통과해야 하며 status와 validated flag를 포함
- matching artifact가 깨진 JSON, schema mismatch, hash mismatch, 잘못된 store bucket에 있으면 검색은 실패
- `--kind`로 artifact 종류를 제한할 수 있으며, 지원하지 않는 종류는 실패
- 검색 결과는 일치한 파일 경로, artifact 종류, status, validated flag, score, snippet을 포함
- 아직 embedding 기반 semantic retrieval이나 외부 registry 검색을 구현한 것으로 주장하지 않음

# Capability Manifest

- capability는 다음과 같은 yaml manifest 형태로 정의

```yaml
name: repo_issue_triage
version: 0.1.0
description: GitHub issue를 분석하고 우선순위, 원인 후보, 수정 계획을 제안하는 capability

inputs:
  - issue_url
  - repository_path
  - target_branch

context:
  required:
    - repository_tree
    - recent_commits
    - related_issues
    - test_results
  optional:
    - previous_fix_patterns
    - owner_preferences

workflow:
  graph: langgraph
  nodes:
    - parse_goal
    - collect_context
    - inspect_code
    - propose_fix
    - run_tests
    - collect_evidence
    - human_review

harness:
  required_checks:
    - unit_test_pass
    - type_check_pass
    - lint_pass
  human_review_required: true

runtime:
  preferred_models:
    - frontier_coding_model
    - local_coder_model
  tools:
    - shell
    - git
    - github
    - file_system

evidence:
  store:
    - prompts
    - tool_calls
    - command_outputs
    - diffs
    - test_results
    - user_feedback

promotion_criteria:
  min_success_runs: 3
  max_human_intervention_rate: 0.3
  required_harness_pass_rate: 0.9
```

# Evidence Schema

- omf에서 evidence는 단순 로그가 아니라 capability 개선을 위한 structured asset으로 관리

## 기본 evidence 항목

- session_id
- capability_id
- user_goal
- normalized_goal
- input_context
- selected_model
- selected_runtime
- tool_calls
- generated_commands
- generated_scripts
- execution_outputs
- errors
- retries
- user_interventions
- final_artifacts
- harness_results
- cost_metrics
- latency_metrics
- success_or_failure_label
- improvement_notes

## evidence 활용 방향

- prompt 개선
- context selection policy 개선
- 실패 케이스 기반 regression eval 생성
- 현재 구현된 regression case는 `omf regress`가 source artifact와 capability manifest를 해시로 묶고 replay를 실제 실행한 JSON artifact다.
- regression case의 inspect는 source artifact와 capability manifest hash link를 다시 검증한다.
- 현재 구현된 learning export는 `omf learn`이 검증된 source artifact를 해시로 묶고 JSONL candidate set과 manifest SHA-256을 저장한 JSON artifact다.
- 모델별 성능 비교
- 작은 모델용 few-shot example 생성
- fine-tuning 또는 preference dataset 후보 생성
- 조직별 best practice와 runbook 자동 축적

# Harness Optimization

- omf의 핵심 차별점은 agent output을 검증 가능한 harness와 결합하는 것
- 좋은 capability는 좋은 prompt가 아니라 좋은 harness를 포함한 실행 단위로 정의

## harness 유형

### deterministic test

- unit test, integration test, type check, lint, schema validation

### behavioral eval

- 특정 입력에 대해 기대 행동을 만족하는지 평가

### rubric-based eval

- 문서, 보고서, 분석 결과물에 대해 기준표 기반 평가

### regression eval

- 과거 실패 케이스가 재발하지 않는지 확인
- 현재 구현된 범위는 `omf regress`가 regression case 생성 시 capability replay를 즉시 실행하고 결과를 artifact에 저장하는 것

### human approval

- 자동 검증이 어려운 업무에 대해 사용자 승인 절차 포함

### cost/latency eval

- capability 수행 비용과 시간 측정

- harness는 최초부터 완전할 필요 없음
- agent 실패와 사용자 개입이 누적될수록 harness가 점진적으로 강화되는 구조 지향

# Context Optimization

- omf는 단순히 모든 정보를 context에 넣는 방식이 아니라, capability별 context policy를 관리
- 작은 모델이나 긴 workflow에서 context pollution을 줄이기 위해 중요 정보, 최근 정보, 실패 이력, 사용자 선호, 실행 환경 정보를 선별 주입

## context policy 구성 요소

- required context
- optional context
- forbidden context
- retrieval query template
- summarization rule
- compression rule
- freshness rule
- source priority
- maximum token budget
- evidence recall strategy

## context 최적화 목표

- 모델별 성능 편차 감소
- 반복 업무에서 매번 동일한 설명을 입력해야 하는 비용 감소
- 현장 업무의 암묵지를 명시적 context asset으로 축적
- 로컬/저성능 모델에서도 충분한 업무 수행 가능성 확보

# Prompt Optimization

- omf의 prompt는 단순 system prompt 또는 instruction template이 아니라 capability의 일부로 관리
- prompt는 evidence와 harness 결과를 바탕으로 지속적으로 개선

## prompt 구성 요소

- role instruction
- task instruction
- context usage rule
- tool usage policy
- output format
- failure handling rule
- self-check rule
- human escalation rule
- safety/permission boundary

## prompt 개선 방식

- 실패한 run에서 누락된 조건 분석
- 사용자 수정사항을 instruction candidate로 추출
- 반복되는 오류를 negative example로 반영
- harness failure를 prompt patch로 연결
- 모델별 prompt variant 관리

# Long-running Workflow Control

## 제어 항목

- max_iterations
- max_runtime
- max_cost
- allowed_tools
- disallowed_tools
- require_approval_before_write
- require_approval_before_external_call
- require_approval_before_destructive_action
- checkpoint_interval
- rollback_strategy
- resume_from_checkpoint

## 상태 관리

- 각 workflow는 현재 goal, sub-goal, node state, evidence, pending approval, failure reason을 저장
- 사용자는 중간 상태를 확인하고, 특정 node부터 재실행 가능
- 실패한 workflow도 evidence로 남겨 다음 실행의 개선 재료로 활용

# Human-in-the-Loop Design

- omf는 human intervention을 실패가 아니라 학습 가능한 signal로 간주
- 사용자가 개입한 지점은 capability의 부족한 부분을 드러내는 중요한 evidence로 저장
- 현재 구현된 범위는 `omf review`로 검증된 omf JSON artifact에 대한 reviewer decision과 note를 review artifact로 저장하는 것

## human review 유형

- approve
- reject
- revise
- add context
- change goal
- change constraint
- mark as reusable
- mark as unsafe
- create regression case

## 사용자 개입을 통해 축적되는 정보

- 조직/개인별 판단 기준
- 결과물의 선호 형식
- 위험한 자동화 경계
- 반복되는 agent 오해
- 현장 업무의 암묵지

# System Architecture

## CLI / Agent Interface

- `omf capture`, `omf promote`, `omf replay`, `omf eval`, `omf list`, `omf inspect`, `omf review`, `omf regress`, `omf learn`, `omf search` 명령 제공
- 기존 coding agent 또는 chat agent와 함께 사용할 수 있는 얇은 command layer 제공

## Workflow Orchestrator

- LangGraph 기반 node orchestration 담당
- 상태 전이, 재시도, 중단, 승인, checkpoint, resume 처리

## Capability Registry

- capability manifest 저장
- versioning, dependency, owner, runtime compatibility, evaluation result 관리

## Evidence Store

- agent run에서 발생하는 모든 structured evidence 저장
- 로그, diff, test result, prompt, user feedback, artifact를 연결 관리

## Context Engine

- capability별 필요한 context를 검색·요약·압축·주입
- repository, docs, logs, previous evidence, user preference 등 다양한 source 연결

## Harness Engine

- test, eval, rubric, schema validation, human approval gate 실행
- capability 품질 측정 및 regression 관리

## Runtime Adapter

- OpenAI, Anthropic, local LLM, Claude Code, Codex, shell, MCP, browser 등 런타임 연결
- 모델/도구별 실행 차이를 capability 상위 계층에서 흡수

## Learning Pipeline

- 현재 구현된 범위는 검증된 omf JSON artifact를 local JSONL learning candidate와 manifest로 export하는 것
- export manifest는 source artifact path/SHA-256/type/status, JSONL path/SHA-256, item count를 기록
- learning export는 `omf inspect`에서 JSONL hash, row schema, row count, manifest item 일치와 source artifact hash/type/status 재검증이 통과해야 유효
- prompt patch, eval set, few-shot example, fine-tuning dataset으로의 실제 적용은 후속 pipeline에서 별도 검증해야 함
- 모델 학습, dataset upload, runtime policy 자동 반영은 아직 출시 기능으로 주장하지 않음

# Data Flow

- 사용자 목표 입력
- goal normalization 및 sub-goal decomposition
- 관련 context 검색 및 압축
- workflow graph 생성 또는 기존 capability 검색
- node 단위 실행
- tool call 및 artifact 생성
- harness 검증
- 실패 시 reflection 및 retry
- 성공 시 evidence 저장
- 반복 성공 시 capability promotion
- 누적 evidence 기반 prompt/context/harness/model 개선

# Success Metrics

## capability reuse rate

- 전체 agent 작업 중 기존 capability를 재사용한 비율

## reproducibility rate

- 동일 또는 유사 입력에 대해 같은 기준의 결과를 재현한 비율

## harness pass rate

- capability 실행 후 검증 기준을 통과한 비율

## human intervention rate

- workflow 완료를 위해 필요한 사용자 개입 빈도

## failure-to-improvement conversion rate

- 실패한 run 중 prompt, context, harness, eval 개선으로 연결된 비율

## cost per successful task

- 성공 작업 1건당 모델/API/실행 비용

## model portability score

- 동일 capability가 서로 다른 모델/런타임에서 유지하는 품질 수준

## time-to-capability

- 반복 작업이 최초 발견된 이후 reusable capability로 승격되기까지 걸린 시간

# MVP Scope

- Phase 1 MVP는 coding agent workflow를 1차 대상으로 설정
- 이유는 실행 로그, diff, test, lint, type check 등 harness 구성이 비교적 명확하기 때문
- MVP에서는 다음 기능에 집중

## 필수 기능

- `omf capture`: agent 작업 command를 실제 실행하고 evidence JSON 저장
- `omf promote`: 성공 evidence의 capability manifest 생성 및 source evidence SHA-256 저장
- `omf replay`: 기존 capability command 재실행, artifact hash 검증, manifest/evidence SHA-256 저장
- `omf eval`: replay 반복 실행, embedded replay 검증 가능한 pass rate artifact 생성
- `omf eval`: replay별 실제 command/harness duration을 집계한 timing summary 생성
- `omf list`: 로컬 store artifact 조회
- `omf inspect`: omf JSON artifact schema 검증, capability/replay/eval/review/regression hash link 검증, learning JSONL hash 검증 및 요약
- `omf review`: 검증된 omf JSON artifact에 대한 reviewer decision 저장
- `omf regress`: source artifact와 capability manifest를 묶고 replay를 실행한 regression case 저장
- `omf learn`: 검증된 omf artifact를 local JSONL learning candidate set으로 export하고 manifest/hash 저장
- `omf search`: 로컬 store JSON artifact에 대한 inspect-validated text-based 검색
- shell/git/test 기반 harness 실행은 `omf capture --check`와 replay 시 check 재실행으로 구현
- Git 기반 작업 이력은 `omf capture`가 수집하는 root, HEAD, branch, changed files, diff hash로 구현
- evidence store 기본 구현
- capability registry 기본 구현
- LangGraph 기반 node workflow prototype은 아직 출시 기능이 아니라 후속 구현 대상

# Product Positioning

- oh-my-field는 “agent를 더 많이 쓰는 도구”가 아니라 “agent가 한 일을 조직의 능력으로 남기는 도구”
- 즉각적인 자동화보다 중요한 것은 반복 가능한 capability 축적
- 프롬프트보다 중요한 것은 context, harness, evidence, learning loop
- 모델 성능보다 중요한 것은 현장 업무 기준에 맞게 agent를 피팅하는 과정
- omf의 핵심 가치는 일회성 agent interaction을 검증 가능한 field capability로 전환하는 것에 있음

# Preferred Environment Configuration

- omf는 특정 모델, 특정 IDE, 특정 agent runtime, 특정 업무 도메인에 강하게 종속되지 않는 것을 지향
- 초기 제품은 범용적인 agent capability 구축 환경을 대상으로 시작하되, 이후 coding, infra operation, data analysis, report generation, domain-specific workflow 등으로 확장 가능한 구조를 우선 선호
- 핵심은 “어떤 환경에서든 agent가 한 작업을 capture하고, 검증하고, reusable capability로 승격할 수 있는 최소 실행 기반”을 제공하는 것

# Default Local Environment

- macOS 또는 Linux 기반 개발 환경 우선 지원
- Python 중심 backend/runtime 구성
- uv 기반 Python dependency 및 virtual environment 관리
- Docker / Docker Compose 기반 로컬 서비스 실행
- Git 기반 작업 이력 및 artifact versioning 관리
- CLI-first 사용 경험 제공
- 로컬 파일시스템 기반 artifact 저장을 기본값으로 제공하되, 추후 object storage 연동 가능

# Agent Runtime

- omf는 다양한 coding agent 및 general-purpose agent와 함께 사용할 수 있는 companion runtime 지향
- Codex, Claude Code, Hermes, OpenCode, OpenAI API, Anthropic API, local LLM runtime 등과 연동 가능한 구조 선호
- 단일 agent provider에 종속되지 않고, capability manifest와 evidence schema를 중심으로 agent 실행 계층을 추상화
- agent는 다음 작업을 수행할 수 있어야 함
  - 사용자 목표 해석
  - 작업 계획 수립
  - 파일 읽기/수정
  - shell command 실행
  - test/lint/type check 실행
  - 실행 결과 해석
  - 실패 원인 분석
  - 사용자 승인 요청
  - 결과물 및 evidence 저장

# Workflow Orchestration

- LangGraph 기반 node workflow 구성을 우선 고려
- 각 workflow는 명확한 node와 state transition으로 표현
- node는 다음과 같은 책임 단위로 분리 가능
  - goal parsing
  - context collection
  - plan building
  - tool execution
  - artifact generation
  - harness running
  - evidence collection
  - reflection
  - human review
  - capability packaging
  - learning export
- workflow는 실패, 재시도, 보류, 사용자 승인, 중단, 재개 상태를 명시적으로 표현해야 함
- omf는 agent의 작업을 “대화 흐름”이 아니라 “상태를 가진 실행 graph”로 관리하는 것을 선호

# Backend

- Python 기반 API 및 workflow runtime 우선
- FastAPI, Litestar 등 ASGI framework 사용 가능
- CLI, MCP server, local API server, web dashboard가 동일한 capability registry와 evidence store를 공유하는 구조 지향
- 업무 도메인별 tool adapter는 독립 모듈로 분리
- agent runtime, tool execution, evidence storage, harness execution은 느슨하게 결합

# Database / Storage

- 초기 MVP에서는 다음 두 가지 모드를 모두 고려
  - lightweight local mode
  - durable team/server mode

## lightweight local mode

- SQLite 또는 local filesystem 기반
- 개인 개발자, 단일 프로젝트, 빠른 prototype에 적합
- 설치와 실행이 쉬워야 함

## durable team/server mode

- PostgreSQL 기반 metadata store
- pgvector 기반 embedding similarity search
- object storage 또는 shared filesystem 기반 artifact 저장
- 여러 workflow run, capability version, evidence bundle, eval result 관리에 적합

## 저장 대상

- capability manifest
- workflow run metadata
- prompts
- context snapshots
- tool calls
- command outputs
- generated scripts
- diffs
- test results
- user feedback
- final artifacts
- harness results
- cost/latency metrics

# Retrieval / Context Engine

- omf는 모든 정보를 context에 무작정 넣는 방식을 지양
- capability별 context policy를 통해 필요한 정보만 선별적으로 주입
- 현재 구현된 초기 retrieval은 `omf search`이며, 로컬 `.omf` store의 JSON artifact를 실제 파일에서 읽고 `omf inspect` 검증을 통과한 matching artifact만 text query 결과로 반환한다.
- context engine은 다음 기능을 제공해야 함
  - 파일/문서 검색
  - 이전 workflow evidence 검색
  - 유사 실패 사례 검색
  - capability별 required context 수집
  - context summarization
  - context compression
  - token budget 관리
  - freshness rule 적용
  - source priority 적용

- 초기에는 text-based retrieval을 우선 지원
- 이후 embedding 기반 semantic retrieval, structured metadata filter, multimodal retrieval 등으로 확장 가능
- 현재 MVP에서 검증된 범위는 local store JSON artifact의 text-based search까지이며, semantic retrieval은 후속 구현 대상
- 중요한 것은 retrieval 자체가 아니라, capability 실행에 필요한 context를 재현 가능하게 구성하는 것

# Harness Engine

- omf는 agent output을 검증 가능한 harness와 결합하는 구조를 선호
- harness는 capability의 성공 여부를 판단하는 품질 게이트 역할 수행
- coding workflow에서는 다음 항목을 우선 지원
  - unit test
  - integration test
  - lint
  - type check
  - build check
  - smoke test
- 문서/운영/분석 workflow에서는 다음 항목을 지원 가능
  - schema validation
  - checklist
  - rubric-based evaluation
  - regression case
  - human approval
  - output completeness check
  - source/evidence requirement check
- omf는 “agent가 답변을 생성했는가”보다 “결과물이 검증 기준을 통과했는가”를 완료 조건으로 삼는 환경을 선호

# Tool Integration

- 기본 tool integration은 다음을 우선 지원
  - shell
  - git
  - filesystem
  - Python script execution
  - test runner
  - package manager
  - HTTP/API client
  - document parser
  - database connector

- MCP 기반 tool integration을 우선 고려
- tool adapter는 capability manifest에 명시되어야 함
- 각 tool은 권한 수준과 실행 조건을 가져야 함
- destructive action, external API call, credential access, production write, paid operation 등은 approval gate를 통해 제어

# Model Configuration

- omf는 모델 성능 차이를 전제로 설계
- 초기 capability 설계, workflow decomposition, harness 생성, report drafting 등에는 frontier model을 사용할 수 있음
- 반복 실행, metadata extraction, formatting, local validation 등은 smaller model 또는 local model로 대체 가능
- capability별 model profile 관리 필요
- model profile 예시
  - planning_model
  - execution_model
  - reflection_model
  - summarization_model
  - evaluation_model
  - local_fallback_model

- 동일 capability가 모델 변경 후에도 어느 정도 재현성을 유지할 수 있도록 prompt, context, harness, evidence를 함께 관리

# Local / Closed-network Mode

- omf는 폐쇄망 또는 제한된 네트워크 환경에서도 실행 가능한 구조를 지향
- 외부 API 호출이 불가능한 경우 local file, internal document, local model, internal package registry, local database를 활용
- capability manifest에는 offline compatibility와 runtime dependency를 명시
- closed-network mode에서는 다음 제약을 기본값으로 둘 수 있음
  - external network disabled
  - local model only
  - local artifact store only
  - internal tool adapter only
  - manual approval required for export

- 이 구조는 보안, 규제, 사내망, 고객사 온프레미스 환경에서 agent workflow를 재현하기 위한 기반이 됨

# Development Interface

- 초기 제품은 CLI-first
- CLI는 사람과 agent가 모두 호출하기 쉬운 command surface 제공
- 주요 명령은 다음을 중심으로 구성
  - `omf capture`
  - `omf promote`
  - `omf replay`
  - `omf eval`
  - `omf list`
  - `omf inspect`
  - `omf review`
  - `omf regress`
  - `omf learn`
  - `omf search`

구현되지 않은 명령은 문서에서 출시 기능처럼 표기하지 않는다. `rollback`, `export`는 실제 command, evidence schema, 검증 테스트가 생긴 뒤에만 문서화한다.

- 이후 web dashboard 또는 desktop workbench를 통해 다음 기능 제공 가능
  - capability registry 조회
  - workflow run history 조회
  - evidence bundle 탐색
  - harness result 확인
  - model/runtime 비교
  - human feedback 입력
  - capability version 관리

# Observability

- 모든 workflow run은 session 단위로 추적
- 현재 CLI evidence는 command input/output, exit code, artifact hash, Git 상태, harness result를 기록
- 현재 `omf replay`와 `omf eval`은 실제 command/harness duration 기반 timing을 기록
- cost, user intervention, node별 graph telemetry는 별도 evidence schema와 검증 테스트가 생긴 뒤에만 출시 기능으로 문서화
- 실패한 작업도 성공 작업과 동일하게 evidence로 저장
- long-running workflow에서는 다음 상태를 확인 가능해야 함
  - current goal
  - current sub-goal
  - current node
  - last successful checkpoint
  - pending approval
  - remaining budget
  - last failure reason
  - generated artifacts
  - next planned action

- observability의 목적은 단순 모니터링이 아니라, 실패한 agent 작업을 다음 capability 개선의 근거로 전환하는 것

# Security / Permission Boundary

- omf는 agent가 장시간 실행되는 것을 전제로 하기 때문에 명시적 권한 경계 필요
- 기본적으로 read-only dry-run을 우선 수행
- write action, destructive command, credential access, external upload, production API call, paid API call 등은 사용자 승인 필요
- capability manifest에는 다음 정보를 명시
  - allowed tools
  - disallowed tools
  - approval-required actions
  - safe execution mode
  - credential scope
  - network policy
  - rollback policy

- agent의 autonomy는 실행 편의가 아니라 검증 가능성과 안전성 안에서 제한적으로 부여되어야 함

# Configuration Philosophy

- omf의 선호 환경은 “agent가 자유롭게 모든 것을 하도록 허용하는 환경”이 아님
- omf는 agent의 작업을 capture, structure, verify, replay, improve할 수 있는 controlled reproducible runtime을 선호
- 좋은 환경 구성은 agent의 자유도를 무한히 넓히는 것이 아니라, 업무 기준에 맞게 실행 경계를 명시하고 재현성을 높이는 것
- 따라서 omf의 환경 구성 원칙은 다음과 같음
  - CLI-first
  - local-first
  - evidence-first
  - harness-first
  - runtime-agnostic
  - model-portable
  - permission-bounded
  - reproducibility-oriented
