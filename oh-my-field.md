# Product Vision

- oh-my-field는 에이전트가 수행한 일회성 작업을 조직과 개인의 반복 가능한 업무 자산으로 전환하는 Field-oriented Agent Capability Platform 지향
- 사용자의 현장 업무 맥락, 암묵지, 시행착오, 검증 기준을 에이전트가 재사용 가능한 형태로 학습·축적·실행할 수 있도록 지원
- 단순 프롬프트 관리 도구가 아닌, 프롬프트·컨텍스트·검증 하네스·증거 수집·학습 신호를 capability package로 연결하는 operating layer 지향
- 프론티어 모델, 로컬 모델, 폐쇄망 모델, 사내 특화 모델 등 런타임이 변경되어도 사용자의 업무 기준과 검증 가능한 실행 품질 유지
- “AI가 한 번 잘한 일”을 “언제든 다시 잘할 수 있는 capability”로 만드는 것에 집중

# Core Concept

## Field

- 사용자가 실제로 업무를 수행하는 도메인 환경
- 예: 코드베이스, 인프라 환경, 사내 운영 프로세스, 데이터 파이프라인, 고객 지원 절차, 보고서 작성 체계 등
- 단순 지식 문서가 아닌, 실행 가능한 업무 맥락과 판단 기준의 집합

## Capability

- 외부 agent runtime에 주입 가능한 repo-local 업무 능력 패키지
- `capability.yaml`, `instructions.md`, `harness.yaml`, 사람이 읽는 capability card, evidence lineage, accepted patch metadata 포함
- 모델·런타임·프로젝트가 바뀌어도 검증 가능한 방식으로 이식되어야 하며, 실패 시 evidence와 patch 후보로 개선 가능한 구조 필요

## Evidence

- 에이전트가 업무를 수행하는 과정에서 생성·수집되는 판단 근거
- 예: 실행 로그, 커맨드 히스토리, 코드 diff, 테스트 결과, 사용자 피드백, 실패 케이스, 재시도 이력, 산출물 품질 평가 등
- 향후 capability 개선, 프롬프트 최적화, 하네스 보강, 모델 fine-tuning 또는 preference 학습의 근거로 활용

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

## 장시간 agent run의 자산화

- 장시간 실행 자체는 Codex, Claude Code, Hermes 등 외부 agent runtime에 위임
- omf는 해당 run에서 생성된 log, diff, test result, artifact, user intervention을 evidence로 수집
- 반복되는 성공/실패를 capability package, regression eval, context policy, learning patch로 전환

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
- 단순 성공 산출물뿐 아니라 외부 runtime이 남긴 실행 흔적과 환경 정보 수집

## 2. Structure

- 수집된 작업을 목표, 입력, 절차, 도구, 산출물, 검증 기준, 실패 조건으로 구조화
- 일회성 agent interaction을 evidence-backed capability package 후보로 변환

## 3. Harness

- capability의 성공 여부를 판단할 수 있는 평가 기준 구성
- 자동 테스트, schema validation, lint, benchmark, checklist, human approval gate 등 설정

## 4. Verify

- 외부 agent가 만든 산출물을 harness 기준으로 검증
- 각 검증 단계는 상태와 evidence를 명시적으로 남김

## 5. Evaluate

- 실행 결과를 harness 기준으로 검증
- 실패 시 원인 분류, context 보강, prompt/harness patch 후보 생성, target runtime 재검증 계획 수립

## 6. Promote

- 검증 가능한 evidence set을 reusable capability package로 승격
- capability registry에 저장하고, 이후 유사 작업이나 다른 runtime export에서 검색·재사용 가능하게 구성

## 7. Learn

- 누적 evidence를 기반으로 prompt optimization, context packing, retrieval policy 개선
- 필요 시 fine-tuning dataset, preference dataset, eval set으로 전환

# LangGraph-based Artifact Pipeline Design

- omf의 LangGraph는 agent가 일을 수행하는 graph가 아니라, agent가 만든 run artifact를 capture, structure, verify, promote, learn 하는 artifact processing pipeline graph
- 각 pipeline은 evidence와 capability package 상태를 가진 graph로 표현
- node는 명확한 artifact 처리 책임 단위로 분리하며, edge는 성공·실패·보류·사용자 승인 등 상태 전이를 표현

## 주요 node 예시

### Import Evidence Node

- 외부 runtime log, diff, test result, artifact를 evidence record로 수집

### Structure Context Node

- evidence와 field policy를 바탕으로 required/optional/forbidden context를 구조화

### Build Harness Node

- 테스트, lint, rubric, checklist, human review gate를 capability harness로 정리

### Verify Integrity Node

- evidence와 capability package의 integrity link를 검증

### Promote Capability Node

- evidence set과 metrics를 canonical package로 승격

### Export Runtime Assets Node

- canonical package를 Codex, Claude Code, Hermes, generic skill bundle로 변환

### Record Learning Patch Node

- failure/review/eval 결과를 prompt, context, harness patch 후보와 decision record로 저장

### Human Review Node

- 사용자 승인, 수정 요청, 중단, 재실행 여부 판단

# Command Interface

이 섹션은 전체 CLI 기능 레퍼런스다. README는 제품 소개, 설치, quick start만
담고, 상세 기능 표면은 이 문서를 기준으로 관리한다.

CLI는 request를 구성하고 JSON summary를 출력하는 표면이다. portability 구현은
`oh_my_field.portability` compatibility shim 뒤에서 다음 구조로 실행된다.

- Domain: `domain/portability/models.py`, `readiness.py`, `lifecycle.py`
- Application: `application/portability/*_workflow.py`
- Runtime export adapters: `adapters/runtime_export/{codex,claude_code,hermes,generic}.py`
- Storage: `infrastructure/portability/{bundle_store,overlay_store,paths}.py`

## /import-run

- Codex, Claude Code, Hermes 등 외부 agent runtime의 run log를 evidence로 import
- log, diff, test result, command output, artifact root를 읽어 EvidenceRecord 생성
- 바이너리/비-UTF-8 artifact는 실패 대신 메타데이터(mime_type, size, sha256)만 기록하고 storage_mode=external로 외부화
- `--max-artifact-bytes`로 큰 artifact를 외부화하고, `--redact-secrets`로 stdout/로그의 api key/token/password/bearer/AWS key를 [REDACTED]로 치환
- OMF가 agent를 실행하는 것이 아니라, 외부 agent가 만든 artifact를 OMF evidence로 가져오는 명령

## /capture

- 현재 agent 작업 세션의 로그, 프롬프트, 결과, 사용자 수정사항을 evidence로 저장
- 실패한 작업도 저장 가능
- 향후 capability 후보로 승격하기 위한 raw material 확보

## /promote

- 특정 evidence record 또는 evidence set을 capability package로 승격
- capability.yaml, instructions.md, harness.yaml, Capability Card, context policy, failure recovery rule 생성

## /replay

- 기존 capability package를 동일/유사 입력에 대해 검증
- 모델·런타임 변경 시 재현성 비교 가능

## /eval

- capability의 성능, 안정성, 비용, 재현성, 사용자 개입률 평가
- 여러 모델 또는 runtime 간 비교 지원

## Portability Lifecycle

capability의 portability 상태는 네 단계로 구분한다. "export 가능"과 "target에서 실제로
동작"을 섞지 않기 위함이다.

- **exported**: capability가 target runtime용 bundle로 변환된 상태 (`/capability export`)
- **imported**: bundle이 target project에 materialized된 상태 (`/capability import`)
- **validated**: 실제 target run이 통과한 상태 (`/capability validate --run-command ...`).
  정적 `import --validate`만으로는 needs_validation에 머문다
- **portable**: 최소 하나 이상의 target import가 validated된 상태

`/health`는 export_status, import_status, validation_status를 분리해 보고하므로 위
상태가 혼동되지 않는다. export는 source package의 `exports/`에, import는
`imports/<target>/target.overlay.yaml`에 흔적을 남긴다.

## /capability export

- canonical capability package를 target runtime/model/project용 portability bundle로 export
- `portability.yaml`, source runtime/model/project metadata, evidence links, context policy, harness metadata 생성
- `provenance/`에 integrity proof와 source evidence pack 생성. `--include-evidence`로 `none|summary|redacted|full` 모드 선택(기본 `summary`)
- source package의 `exports/<target>/export.yaml`에 export 흔적 기록
- export workflow는 `adapters/runtime_export` registry에서 target adapter를 찾아 runtime-specific files를 생성
- Codex target은 `AGENTS.md`, `capability.md`, `context.policy.md`, `harness.md` 생성
- Claude Code target은 `CLAUDE.md`, `capability.md`, `examples.md`, `checks.md` 생성
- Hermes target은 `SOUL.md`, `skills/<capability>.md`, `profile.patch.yaml`, `harness.md` 생성
- generic target은 `skill.md`, `context.policy.yaml`, `harness.yaml`, `eval_set.yaml` 생성

## /capability import

- portability bundle을 target project capability directory로 import (canonical `capability.yaml`은 source 기준 유지)
- target 상태는 `imports/<target>/`에 분리 기록: `target.overlay.yaml`, `validation_report.yaml`, target용 `README.md`/`instructions.md`/`context.pack.md`
- target.overlay에는 status, tool compatibility, portability readiness score, instruction/context variant, human review override 기록
- `--validate` 사용 시 target-side eval result를 자동 생성하고, 실패한 target validation을 evidence로 수집
- `--as`로 이름 변경, `--namespace`로 하위 디렉터리 격리, `--if-exists fail|merge|version|overwrite`로 충돌 정책 선택(기본 fail; version은 `<name>_vN`로 분기)
- validation report에는 portability readiness breakdown(score, required_pass_rate, factor별 delta/reason), source/target model delta, compact instruction, compressed context path 기록

## /capability validate

- import된 capability를 동일 target에 대해 재검증(import와 validation을 분리). overlay를 읽어 portability를 재구성하고 overlay/validation report를 덮어씀
- `--run-command`로 target runtime hook을 제공하면 해당 명령을 안전 실행 머신러리로 실행(`--approve-command-risk`로 risk 승인)하고 exit code를 target eval에 반영. OMF는 agent runtime을 직접 구현하지 않고 결과만 수집
- `--run-command` 없이 실행하면 manual_run_required와 expected_artifacts를 기록해 사용자가 직접 실행 후 `import-run`으로 결과를 가져오도록 안내
- 정적 검사만 통과하면 status는 needs_validation에 머물고, 실제 target run이 통과해야 validated로 승격. tool 누락/readiness 미달이거나 실제 run이 실패하면 needs_adaptation + failure evidence
- export → import → validate → adapt → validate again 루프를 형성

## /capability remap

- target import의 project/context remap을 boolean이 아니라 실제 plan 객체로 기록
- `--map key=value`로 target binding을, `--unresolved`로 미해결 항목을 선언해 `imports/<target>/context.remap.yaml` 생성
- unresolved가 비어 있으면(complete) `/capability validate`가 context remap을 해결된 것으로 간주해 context_remap 검사를 통과시킴
- project portability를 "다른 프로젝트라고 표시"에서 "실제 매핑"으로 끌어올림

## /capability adapt

- target overlay의 adaptation을 적용: `--instruction-variant base|compact`, `--context-variant full|compressed`, `--require-human-review/--no-require-human-review`
- 선택한 variant로 `instructions.md`/`context.pack.md`를 재생성하고 overlay overrides를 갱신
- 이후 `/capability validate`는 overrides를 재계산하지 않고 보존하므로 export → import → validate → adapt → validate 루프가 일관됨

## /health

- capability 상태, evidence/eval/integrity/portability 요약과 next action 표시
- `registry`보다 운영자가 읽기 쉬운 health surface 제공

## /harden

- regression case, eval, learning patch, runtime export 등 다음 hardening action 추천
- 사용자가 advanced command를 모두 외우지 않아도 capability 강화 루프를 진행할 수 있게 함

## /card

- capability package의 `README.md` Capability Card를 읽거나 재생성
- 사람이 읽는 capability 요약을 CLI에서 바로 확인 가능

## /regression-case

- 과거 실패나 중요한 기대 행동을 versioned eval set의 regression case로 기록
- eval set은 이후 `/eval --eval-set`에서 재발 방지 기준으로 사용

## /approve, /reject, /revise, /review

- evidence, capability, replay, eval 대상에 human review signal 기록
- approve/reject/revise는 자주 쓰는 action shortcut
- review는 add_context, change_goal, mark_unsafe, create_regression_case 등 구조화된 review action 처리

## /learn

- capability와 누적 evidence에서 prompt/context/harness 개선 후보를 learning export로 생성
- 자동으로 capability를 수정하지 않고, patch 후보를 검토 가능한 artifact로 남김

## /learn-patch

- learning export의 prompt/context/harness patch 후보를 accept/reject
- accepted patch는 capability package metadata에 기록하고, rejected patch도 decision record로 보존

## /dataset-export

- learning export, learning patch decision, eval result를 JSONL dataset으로 변환
- fine-tuning, preference, eval dataset을 `.omf/datasets/<capability>/` 아래에 생성
- 각 row는 source learning/eval/decision id를 보존하여 학습 데이터 provenance를 추적 가능하게 유지

## /verify

- evidence, capability, replay, eval, context, learning, review, export artifact의 integrity link 검증
- capability가 참조하는 source evidence lineage가 변조되지 않았는지 확인

## /registry

- capability registry를 조회하고 상태, eval count, pass rate, runtime coverage, integrity status 요약
- 여러 capability를 운영할 때 health surface의 목록형 보기로 사용

## /reflect

- capability evidence와 eval result에서 failure category, retry strategy, patch 후보를 reflection report로 생성
- 실패한 run을 다음 hardening action으로 연결하기 위한 분석 surface

## /run

- local OMF artifact pipeline을 한 번에 처리하는 advanced/dev 명령
- capture, promote, context pack, replay, eval, learn artifact를 생성하지만 agent runtime을 대체하지 않음
- 제품 quick start의 main flow는 `/import-run → /promote → /health`

## /status, /resume, /rollback

- advanced local artifact pipeline run의 상태를 확인, 재개, 특정 artifact node로 rollback
- rollback node는 capability asset lifecycle 기준 이름을 사용: import_evidence, promote_capability, pack_context, run_verification, evaluate_capability, record_learning_patch

## /dashboard

- local HTML dashboard와 JSON snapshot API 제공
- workflow state, approval request, review, eval, registry health를 한 화면에 요약
- capability health, portability export/import/validation, learning patch decision 상태를 시각화

## /inspect

- evidence, capability, replay, eval, workflow/run, export, import, context, learning, reflection artifact를 read-only로 조회
- imported target은 `--target`, `--model`로 특정 runtime/model overlay를 지정 가능
- 디버깅과 audit 확인을 위한 low-level inspection surface

## /diff

- evidence, capability, harness, learning-patch artifact 간 unified diff 출력
- capability/harness는 두 capability name 또는 `--from-capabilities-dir`, `--to-capabilities-dir`로 같은 capability의 두 저장 위치 비교
- version history가 별도 저장되기 전까지는 이미 존재하는 artifact/package 간 비교를 수행

## /explain, /why

- capability rule, harness check, learning-patch decision이 어떤 evidence와 patch decision에서 왔는지 설명
- `why`는 `explain`의 alias
- 현재 저장된 capability/evidence/learning-patch metadata를 기반으로 설명하며, 외부 추론은 수행하지 않음

## /export

- capability와 관련 evidence/eval/context/learning/reflection artifact를 approval-gated bundle로 export
- runtime-specific portability export는 `/capability export`를 사용

## Command Grouping

- Create: `import-run`, `capture`, `promote`
- Harden: `harden`, `regression-case`, `eval`, `learn`, `learn-patch`, `dataset-export`
- Port: `capability export`, `capability import`, `capability validate`, `capability remap`, `capability adapt`
- Operate: `health`, `registry`, `dashboard`, `verify`
- Review: `approve`, `reject`, `revise`, `review`
- Advanced: `replay`, `context`, `reflect`, `inspect`, `diff`, `explain`, `why`, `rollback`, `resume`, `run`, `export`

# Capability Package

- capability는 단일 manifest가 아니라 폴더 단위 package로 정의

```text
capabilities/
  repo_issue_triage/
    capability.yaml
    instructions.md
    harness.yaml
    README.md
    examples/
    eval_sets/
    patches/
    provenance/
    exports/
```

- `capability.yaml`은 canonical metadata
- `instructions.md`는 agent runtime에 주입 가능한 runtime-neutral instruction surface
- `harness.yaml`은 검증 기준과 approval boundary
- `README.md`는 사람이 읽는 Capability Card

`capability.yaml`은 다음 형태를 기본으로 함.

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
    - import_evidence
    - pack_context
    - run_verification
    - record_review
    - export_runtime_assets
    - apply_learning_patch

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

# Artifact Pipeline Control

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

- 각 pipeline run은 현재 artifact node, evidence, pending approval, failure reason을 저장
- 사용자는 중간 상태를 확인하고, 특정 artifact processing node부터 재실행 가능
- 실패한 외부 agent run도 evidence로 남겨 다음 package 개선 재료로 활용

# Human-in-the-Loop Design

- omf는 human intervention을 실패가 아니라 학습 가능한 signal로 간주
- 사용자가 개입한 지점은 capability의 부족한 부분을 드러내는 중요한 evidence로 저장

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

- /capture, /promote, /replay, /eval 등 명령 제공
- 기존 coding agent 또는 chat agent와 함께 사용할 수 있는 얇은 command layer 제공

## Artifact Pipeline Orchestrator

- LangGraph 기반 artifact processing node orchestration 담당
- capture, structure, verify, promote, learn 단계의 상태 전이, 중단, 승인, checkpoint, resume 처리

## Capability Registry

- capability package metadata 저장
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

## Agent Importer

- Codex, Claude Code, Hermes 등 외부 agent runtime의 run artifact import 담당
- Codex / Claude Code / Hermes 같은 외부 agent runtime은 직접 재구현하지 않고, run log, diff, test result, command output, artifact를 evidence로 import하는 importer를 제공
- runtime matrix replay/eval은 capability portability를 검증하기 위한 artifact를 생성하며, agent 자체의 장시간 실행 loop를 대체하지 않음
- 외부 runtime adapter는 `oh_my_field.adapters.RuntimeAdapter` protocol과 동일한 `spec`, `import_run()` surface를 구현
- Python package entry point group `oh_my_field.runtime_adapters`에 adapter factory/object를 등록하면 `import-run` dispatch registry에 자동 포함

## Runtime Exporter

- canonical capability package를 외부 agent runtime별 instruction/skill bundle로 변환
- export adapter는 `oh_my_field.adapters.runtime_export.RuntimeExportAdapter` protocol을 따르고, log import adapter와 분리된다
- export workflow는 canonical bundle/provenance를 먼저 만들고 registry lookup 결과로 runtime projection만 렌더링한다
- Codex target은 `AGENTS.md`, capability instruction, context policy, harness guide 생성
- Claude Code target은 `CLAUDE.md`와 project memory style instruction 생성
- Hermes target은 `SOUL.md`, skill markdown, profile patch 생성
- Generic target은 `skill.md`, `context.policy.yaml`, `harness.yaml` 생성

## Learning Pipeline

- evidence를 prompt patch, eval set, few-shot example, fine-tuning dataset으로 변환
- 모델 학습 또는 runtime policy 개선에 활용
- prompt patch뿐 아니라 context patch와 harness patch도 accept/reject decision을 거쳐 capability package에 반영
- patch decision은 before/after eval, pass-rate delta, reviewer note, integrity link를 보존

# Data Flow

- 외부 agent runtime이 사용자 목표를 수행
- omf가 run log, diff, test result, command output, artifact를 evidence로 import
- evidence에서 goal, context, runtime metadata, harness signal, user intervention 추출
- required/optional/forbidden context policy 구성
- harness 검증과 integrity verification 수행
- 실패 시 reflection 및 patch 후보 생성
- 검증 가능한 evidence set을 capability package로 promotion
- promotion은 success run count, harness pass rate, human intervention rate, retry rate, runtime profile, eval pass rate를 계산해 candidate / validated / stable 상태를 산출
- 누적 evidence 기반 prompt/context/harness/model 개선
- integrity verification은 evidence → capability → replay → eval → review → learning/export lineage가 변조되지 않았는지 확인

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
- validated target import의 eval pass rate로 측정하며, export 시 계산하는 heuristic portability readiness score(이식 난이도 진단)와는 구분한다

## time-to-capability

- 반복 작업이 최초 발견된 이후 reusable capability로 승격되기까지 걸린 시간

# MVP Scope

- Phase 1 MVP는 coding agent workflow를 1차 대상으로 설정
- 이유는 실행 로그, diff, test, lint, type check 등 harness 구성이 비교적 명확하기 때문
- MVP에서는 다음 기능에 집중

## 필수 기능

- /capture: agent 작업 세션 수집
- /import-run: 외부 agent runtime run artifact를 evidence로 import
- /promote: 검증 가능한 evidence의 capability package 생성
- /replay: 기존 capability 재실행
- evidence store 기본 구현
- capability registry 기본 구현
- shell/git/test 기반 harness 실행
- LangGraph 기반 artifact pipeline prototype

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

# Agent Runtime Integration

- omf는 다양한 coding agent 및 general-purpose agent와 함께 사용할 수 있는 companion operating layer 지향
- Codex, Claude Code, Hermes, OpenCode, OpenAI API, Anthropic API, local LLM runtime 등과 연동 가능한 구조 선호
- 단일 agent provider에 종속되지 않고, capability package와 evidence schema를 중심으로 import/export 계층을 추상화
- 외부 agent runtime은 다음 작업을 수행하고, omf는 그 결과물을 evidence로 수집
  - 사용자 목표 해석
  - 작업 계획 수립
  - 파일 읽기/수정
  - shell command 실행
  - test/lint/type check 실행
  - 실행 결과 해석
  - 실패 원인 분석
  - 사용자 승인 요청
  - 결과물 및 evidence 저장

# Artifact Pipeline Orchestration

- LangGraph 기반 artifact pipeline 구성을 우선 고려
- 각 pipeline은 명확한 node와 state transition으로 표현
- node는 다음과 같은 책임 단위로 분리 가능
  - evidence import
  - context packaging
  - harness building
  - integrity verification
  - artifact generation
  - reflection
  - human review
  - capability packaging
  - runtime export
  - learning export
- pipeline은 실패, 보류, 사용자 승인, 중단, 재개 상태를 명시적으로 표현해야 함
- omf는 agent의 작업을 직접 실행하기보다, agent가 만든 artifact를 “상태를 가진 검증 graph”로 관리하는 것을 선호

# Backend

- Python 기반 API 및 artifact processing runtime 우선
- FastAPI, Litestar 등 ASGI framework 사용 가능
- CLI, MCP server, local API server, web dashboard가 동일한 capability registry와 evidence store를 공유하는 구조 지향
- 업무 도메인별 tool connector는 독립 모듈로 분리
- agent runtime import/export, evidence storage, harness verification은 느슨하게 결합

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

- capability package metadata
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
- tool connector는 capability package metadata에 명시되어야 함
- 각 tool은 권한 수준과 실행 조건을 가져야 함
- destructive action, external API call, credential access, production write, paid operation 등은 approval gate를 통해 제어

# Model Configuration

- omf는 모델 성능 차이를 전제로 설계
- 초기 capability 설계, context/harness 구성, report drafting 등에는 frontier model을 사용할 수 있음
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
- capability package에는 offline compatibility와 runtime dependency를 명시
- closed-network mode에서는 다음 제약을 기본값으로 둘 수 있음
  - external network disabled
  - local model only
  - local artifact store only
  - internal tool connectors only
  - manual approval required for export

- 이 구조는 보안, 규제, 사내망, 고객사 온프레미스 환경에서 agent workflow를 재현하기 위한 기반이 됨

# Development Interface

- 초기 제품은 CLI-first
- CLI는 사람과 agent가 모두 호출하기 쉬운 command surface 제공
- 사용자-facing 문서는 다음 mental model 기준으로 명령을 그룹화
  - Create: import-run, capture, promote
  - Harden: harden, regression-case, eval, learn, learn-patch, dataset-export
  - Port: capability export, capability import, capability validate, capability remap, capability adapt
  - Operate: health, registry, dashboard, verify
  - Review: approve, reject, revise, review
  - Advanced: replay, context, reflect, inspect, diff, explain, why, rollback, resume, run, export
- 첫 사용자 흐름은 import-run → promote → health를 기본 quick start로 제시
- context, verify, learn-patch, regression-case, run은 advanced/hardening surface에서 설명

- 이후 web dashboard 또는 desktop workbench를 통해 다음 기능 제공 가능
  - capability registry 조회
  - workflow run history 조회
  - evidence bundle 탐색
  - harness result 확인
  - model/runtime 비교
  - human feedback 입력
  - capability version 관리
  - approval/review/regression case action 생성
  - promotion metrics, matrix coverage, patch count, integrity status 확인

# Observability

- 모든 imported run과 artifact pipeline run은 session 단위로 추적
- node별 input, output, error, retry, latency, cost, artifact, user intervention 기록
- 실패한 작업도 성공 작업과 동일하게 evidence로 저장
- artifact pipeline에서는 다음 상태를 확인 가능해야 함
  - current node
  - last successful checkpoint
  - pending approval
  - last failure reason
  - generated artifacts
  - next planned action

- observability의 목적은 단순 모니터링이 아니라, 실패한 agent 작업을 다음 capability 개선의 근거로 전환하는 것

# Security / Permission Boundary

- omf는 agent가 만든 artifact를 검증하고 이식하는 도구이므로 명시적 권한 경계 필요
- 기본적으로 read-only dry-run을 우선 수행
- write action, destructive command, credential access, external upload, production API call, paid API call 등은 사용자 승인 필요
- capability package에는 다음 정보를 명시
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
- omf는 agent가 만든 artifact를 capture, structure, verify, replay, improve할 수 있는 controlled reproducible artifact environment를 선호
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
