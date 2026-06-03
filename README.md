<p align="center">
  <img src="assets/oh-my-field-logo.png" alt="oh-my-field logo" width="760">
</p>

# oh-my-field

Field-fit agents to real work. oh-my-field turns one-off agent sessions into
portable, evidence-backed capability packages.

Most agent tools help you run the next prompt. oh-my-field focuses on what
happens after an agent does useful work: import the run, preserve the evidence,
define the harness, review it, and promote it into a capability package that can
be exported across models, tools, and operating environments.

## Product Philosophy

oh-my-field is a field-oriented agent capability platform. Its core belief is
that "the agent answered" is not enough. A valuable agent workflow should leave
behind structured evidence, explicit context, reproducible execution steps, and
a harness that can verify whether the result meets the user's real work
standard.

The product is designed around a few principles:

- A field is more than a knowledge base. It includes the local codebase,
  operating process, constraints, review preferences, failure history, and
  quality bar that shape how work should be done.
- A capability is more than a prompt template. It is a repo-local package with
  `capability.yaml`, `instructions.md`, `harness.yaml`, a human-readable card,
  evidence links, and learning metadata.
- Evidence is a product asset. Failed runs, user corrections, command outputs,
  test results, diffs, and review notes become raw material for better future
  runs.
- Harnesses are the quality gate. Tests, lint checks, type checks, rubric
  scores, checklists, and human approval rules decide whether a workflow is
  actually fit for the field.
- Runtime portability matters. A capability should be useful even when the
  model, coding agent, local environment, or deployment setting changes.

The goal is not to automate every task blindly. The goal is to make repeated
agent work inspectable, reviewable, reusable, and progressively better.

This README is the external user guide for installing and operating the CLI.
The deeper product specification and roadmap live in `oh-my-field.md`.

## Who It Is For

oh-my-field is built for technical users who are already using agents in real
work and want those runs to compound instead of disappearing into chat history.

- AI and agent engineers who need repeatable workflows, evaluation harnesses,
  and improvement loops.
- Field domain experts who want their tacit process knowledge and review
  criteria reflected in agent behavior.
- DevOps, infrastructure, and platform engineers who care about auditability,
  command risk, approval boundaries, and reproducibility.
- Small teams and startup operators who want a local capability library instead
  of rewriting the same prompt and context every time.

## Non-Goals

oh-my-field is not:

- A general AGI system.
- A prompt marketplace.
- A wrapper around one specific model provider or coding agent.
- An autonomous-only system that removes human review.
- A tool that asks users to trust unverified agent output.

## Core Concepts

### Field

The working environment where the user actually performs the task. A field can
be a codebase, infrastructure environment, internal runbook, data pipeline,
support process, reporting workflow, or any other domain where judgment and
context matter.

### Capability

A repo-local package that can be given to an external agent runtime. A
capability includes runtime-neutral instructions, captured context policy,
runtime metadata, verification harness, evidence links, human review policy,
and learning metadata needed to repeat or improve a workflow.

### Evidence

Structured records from agent work. Evidence can include prompts, context files,
tool calls, command outputs, diffs, test results, artifacts, feedback, user
interventions, retries, and improvement notes.

### Harness

The checks used to decide whether a result is acceptable. For code work, that
often means tests, lint, type checks, or smoke commands. For operational or
document workflows, it can include checklist items, rubric scores, schema
validation, and human approval.

### Runtime

The model, tools, and execution environment used by the agent. oh-my-field is
designed to record runtime details without making the capability depend on a
single provider or interface.

## Requirements

This repository currently documents the source-based installation path only.
Use `uv sync` and `uv run omf ...` from a local checkout.

Runtime requirements:

- Python `>=3.12`
- `uv`

Project dependencies:

- `langgraph`
- `pydantic`
- `pyyaml`
- `typer`

Development dependencies:

- `pytest`
- `ruff`
- `pyright`
- `types-pyyaml`

## Install From Source

Clone the repository, install dependencies, and run the local CLI through `uv`.

```bash
git clone https://github.com/Baekpica/oh-my-field.git
cd oh-my-field
uv sync
uv run omf --help
```

The console script is registered as `omf` in `pyproject.toml`:

```toml
[project.scripts]
omf = "oh_my_field.cli:app"
```

Use `uv run omf ...` for the documented source workflow.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

The project uses strict Pyright settings and Ruff linting. Keep changes small
and verify command behavior with the CLI when editing documentation or command
plumbing.

## Safety Model

oh-my-field records command intent and risk. Commands classified as write,
destructive, external, credential, production, or paid risk are recorded but not
executed unless the command receives explicit approval.

Use `--approve-command-risk` only when you intentionally want a risky command to
execute.

```bash
uv run omf capture \
  --goal "approved file write" \
  --command "touch /private/tmp/omf-approved-write" \
  --approve-command-risk \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

Exports are also gated. `omf export` refuses to create an export bundle unless
`--approve-export` is passed.

```bash
uv run omf export repo_issue_triage \
  --approve-export \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --eval-dir /private/tmp/omf-evals-smoke \
  --context-dir /private/tmp/omf-context-smoke \
  --learning-dir /private/tmp/omf-learning-smoke \
  --reflection-dir /private/tmp/omf-reflections-smoke \
  --export-dir /private/tmp/omf-exports-smoke
```

## Core Workflow

The typical path is:

1. Import a real agent run as evidence.
2. Promote the evidence into a capability package.
3. Replay the capability to check reproducibility.
4. Build a context bundle from required and optional evidence.
5. Evaluate the capability with harness commands, checklists, or rubrics.
6. Record human review signals such as approval, rejection, revision, added
   context, unsafe markers, or regression cases.
7. Learn from the accumulated evidence and evaluation results.
8. Accept or reject learning patches before they update the package.
9. Inspect or export artifacts when they are ready to share or archive.

For local artifact processing, `omf run` can combine capture, promotion, context
packing, replay, evaluation, and learning in one workflow record. It is an
advanced OMF pipeline command, not an agent runtime replacement.

## Using With Agent Runtimes

oh-my-field does not replace Codex, Claude Code, or Hermes. Let the agent do
the work, then import the run log and generated artifacts into OMF.

Codex example:

```bash
uv run omf import-run codex \
  --log /private/tmp/codex-run.log \
  --goal "ship the parser fix" \
  --diff /private/tmp/codex.diff \
  --test-result /private/tmp/pytest.txt \
  --artifact-root /private/tmp/codex-artifacts \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

Claude Code example:

```bash
uv run omf import-run claude_code \
  --log /private/tmp/claude-code.log \
  --goal "triage failing import test" \
  --command-output /private/tmp/claude-stdout.log \
  --artifact-root /private/tmp/claude-code-artifacts \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

Hermes example:

```bash
uv run omf import-run hermes \
  --log /private/tmp/hermes-run.log \
  --goal "prepare release rollback evidence" \
  --diff /private/tmp/hermes.patch \
  --test-result /private/tmp/hermes-tests.txt \
  --artifact-root /private/tmp/hermes-artifacts \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

`--artifact-root` scans a file or directory and infers artifact roles from
filenames: `.diff` and `.patch` become diffs, test/pytest/junit/coverage files
become test results, stdout/stderr/output/log files become command outputs, and
everything else is preserved as an artifact.

## Artifact Directories

The default local artifact locations are:

- `.omf/evidence` for captured evidence records.
- `capabilities` for capability packages. Each package contains
  `capability.yaml`, `instructions.md`, `harness.yaml`, and `README.md`.
- `.omf/replays` for replay records.
- `.omf/evals` for evaluation results.
- `.omf/context` for context bundles.
- `.omf/learning` for learning exports.
- `.omf/learning_patches` for accepted or rejected learning patch decisions.
- `.omf/eval_sets` for regression eval sets.
- `.omf/reflections` for reflection reports.
- `.omf/reviews` for human review records.
- `.omf/workflows` for orchestrated workflow runs.
- `.omf/exports` for export bundles.

Examples in this README use `/private/tmp/...` directories so they can be run
without modifying the repository's normal artifact folders.

If you re-run an example and hit an overwrite refusal, change the temp directory
suffix or capability name and run it again.

## Quick Start

The first product loop is three commands: import an external agent run, promote
the evidence into a package, then inspect registry health.

```bash
uv run omf import-run codex \
  --log /private/tmp/codex-run.log \
  --goal "triage repo issue" \
  --test-result tests/fixtures/pytest.txt \
  --evidence-dir /private/tmp/omf-evidence-smoke

uv run omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "GitHub issue triage capability" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke

uv run omf registry repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```

`promote` creates `capabilities/<name>/capability.yaml`, `instructions.md`,
`harness.yaml`, and `README.md`. The package is the canonical source of truth;
runtime-specific files are export targets, not the capability itself.

## Portability Loop

Export a capability package for another runtime/model/project:

```bash
uv run omf capability export repo_issue_triage \
  --target hermes \
  --target-model qwen3.6-27b \
  --source-project source-repo \
  --target-project target-repo \
  --out /private/tmp/repo_issue_triage-hermes-qwen36 \
  --capabilities-dir /private/tmp/omf-capabilities-smoke
```

The bundle includes `capability.yaml`, `portability.yaml`, runtime export
assets, instructions, context policy, harness, and provenance metadata.

Import the bundle in the target project and write an initial validation report:

```bash
uv run omf capability import /private/tmp/repo_issue_triage-hermes-qwen36 \
  --runtime hermes \
  --model qwen3.6-27b \
  --project target-repo \
  --available-tool shell \
  --available-tool file_system \
  --validate \
  --capabilities-dir /private/tmp/target-omf-capabilities
```

Import creates a local package and
`capabilities/<name>/imports/<runtime-model>/validation_report.yaml`. The report
records source/target runtime metadata, tool compatibility, context remap needs,
the regression eval set to run next, and whether the target package needs
adaptation before validation.

## Hardening Example

After the package exists, replay and evaluate it when you are ready to harden
the capability:

```bash
uv run omf replay repo_issue_triage \
  --execute \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke

uv run omf eval repo_issue_triage \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "schema includes reviewer" \
  --rubric-score "clarity:4:5:3:clear enough" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```

## Advanced Local Pipeline Example

`omf run` is an advanced local pipeline command for creating OMF artifacts in
one pass. It is not an agent runtime replacement; Codex, Claude Code, Hermes, or
another agent should still perform the original work.

```bash
uv run omf run \
  --goal "triage repo issue" \
  --name repo_issue_triage_v2 \
  --description "GitHub issue triage capability" \
  --prompt tests/fixtures/prompt.md \
  --command "printf 'orchestrated smoke ok\n'" \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "operator rubric attached" \
  --rubric-score "quality:4:5:3:usable" \
  --runtime-tool shell \
  --evidence-dir /private/tmp/omf-run-evidence-smoke \
  --capabilities-dir /private/tmp/omf-run-capabilities-smoke \
  --replay-dir /private/tmp/omf-run-replays-smoke \
  --eval-dir /private/tmp/omf-run-evals-smoke \
  --context-dir /private/tmp/omf-run-context-smoke \
  --learning-dir /private/tmp/omf-run-learning-smoke \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

The command prints JSON with a `run_id`. Inspect the workflow state:

```bash
uv run omf status <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke

uv run omf inspect workflow <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

If a run needs to be moved back to a previous node for review or rerun, use
`rollback`:

```bash
uv run omf rollback <run_id> \
  --to-node execute_replay \
  --reason "rerun command with approval" \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

## CLI Reference

All commands emit JSON summaries.

### `omf capture`

Capture a real or reconstructed agent run as an evidence record.

Common inputs:

- `--goal`: Required user goal.
- `--prompt`, `--context`, `--tool-call`, `--command-output`, `--diff`,
  `--test-result`, `--artifact`: File inputs to preserve with a role.
- `--command`: Command text to record or execute.
- `--command-cwd`: Command working directory.
- `--command-timeout-seconds`: Command timeout, default `60`.
- `--approve-command-risk`: Execute risky commands instead of recording them as
  blocked.
- `--feedback`, `--user-intervention`, `--final-artifact`,
  `--improvement-note`: Human and result metadata.
- `--outcome`: `success`, `failure`, or `unknown`.
- `--runtime-tool`, `--field`, `--runtime`, `--model`: Runtime metadata.
- `--evidence-dir`: Evidence output directory.

Example:

```bash
uv run omf capture \
  --goal "capture failed run" \
  --command "printf 'failure evidence\n'" \
  --runtime-tool shell \
  --outcome failure \
  --improvement-note "add regression coverage" \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

### `omf promote`

Promote one evidence record, or a YAML evidence set, into a capability package.

```bash
uv run omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "GitHub issue triage capability" \
  --version 0.1.0 \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --eval-dir /private/tmp/omf-evals-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke
```

Evidence set files may be a YAML list of ids or a mapping with `evidence_ids`:

```yaml
evidence_ids:
  - 20260602T010203Z-deadbeef
  - 20260602T010204Z-feedface
```

```bash
uv run omf promote \
  --from-evidence-set /private/tmp/omf-evidence-set.yaml \
  --name repo_issue_triage \
  --description "GitHub issue triage capability" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke
```

The generated package includes field policy, context source planning, promotion
criteria, calculated promotion metrics, source evidence ids, accepted patch
history, artifact integrity links, runtime-neutral instructions, a harness file,
and a human-readable capability card. Passing evidence sets become `validated`;
passing evidence plus matching eval results can become `stable`.

### `omf replay`

Replay a capability against its source evidence. Add `--execute` to execute
captured commands during replay.

```bash
uv run omf replay repo_issue_triage \
  --execute \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --replay-dir /private/tmp/omf-replays-smoke
```

Use `--approve-command-risk` only when replay should execute commands that
require approval.

Use `--matrix` to create one replay record per runtime profile:

```bash
uv run omf replay repo_issue_triage \
  --matrix codex,claude_code,hermes \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --replay-dir /private/tmp/omf-replays-smoke
```

### `omf context`

Build a context bundle for a capability.

```bash
uv run omf context repo_issue_triage \
  --include-optional \
  --query "triage" \
  --max-chars 4000 \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --context-dir /private/tmp/omf-context-smoke
```

### `omf eval`

Evaluate a capability with source evidence, optional replay evidence, harness
commands, checklist items, and rubric scores.

Rubric scores use:

```text
name:score:max_score:pass_threshold[:message]
```

Example:

```bash
uv run omf eval repo_issue_triage \
  --replay-id <replay_id> \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "schema includes reviewer" \
  --checklist-fail "missing regression case" \
  --rubric-score "clarity:4:5:3:clear enough" \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --replay-dir /private/tmp/omf-replays-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```

Use `--matrix` to create one eval result per runtime profile:

```bash
uv run omf eval repo_issue_triage \
  --matrix frontier,local \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --replay-dir /private/tmp/omf-replays-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```

Use `--eval-set` to attach a stored regression suite to an eval result.
Required expected checks fail the eval unless they are observed in checklist,
rubric, or harness check output. Flaky expected checks are recorded without
blocking the eval.

### `omf regression-case`

Create or update a versioned regression eval set.

```bash
uv run omf regression-case repo_issue_triage \
  --eval-set repo_issue_regression \
  --case-id failed_import_case \
  --input "issue=ImportError" \
  --check "identifies_root_cause" \
  --flaky-check "uses_minimal_context" \
  --eval-set-dir /private/tmp/omf-eval-sets-smoke
```

### `omf approve`, `omf reject`, and `omf revise`

Convenience review commands for evidence, capability, replay, and eval targets.

```bash
uv run omf approve capability repo_issue_triage \
  --reviewer operator \
  --note "meets field criteria" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf reject replay <replay_id> \
  --note "runtime behavior diverged" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf revise evidence <evidence_id> \
  --revision "add a regression harness for the observed failure" \
  --review-dir /private/tmp/omf-reviews-smoke
```

### `omf review`

General human-review command. Supported actions are `approve`, `reject`,
`revise`, `add_context`, `change_goal`, `change_constraint`, `mark_reusable`,
`mark_unsafe`, and `create_regression_case`.

```bash
uv run omf review evidence <evidence_id> add_context \
  --added-context "prefer small diffs" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf review replay <replay_id> mark_unsafe \
  --note "destructive command attempted" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf review evidence <evidence_id> create_regression_case \
  --regression-case "parser should reject empty branch" \
  --review-dir /private/tmp/omf-reviews-smoke
```

### `omf learn`

Create a learning export from a capability and its accumulated evidence.

```bash
uv run omf learn repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --learning-dir /private/tmp/omf-learning-smoke
```

### `omf learn-patch`

Accept or reject a prompt, context, or harness patch from a learning export.
Accepted patches are recorded in the capability package; rejected patches are
preserved as decision records.

```bash
uv run omf learn-patch repo_issue_triage \
  --learning-id <learning_id> \
  --patch-index 1 \
  --patch-kind prompt \
  --decision accept \
  --reviewer operator \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --learning-dir /private/tmp/omf-learning-smoke \
  --learning-patch-dir /private/tmp/omf-learning-patches-smoke
```

### `omf import-run`

Import an external Codex, Claude Code, or Hermes run log as evidence. The log is
captured as an artifact, and generated diffs, test results, or additional
artifacts can be attached in the same record. Use `--artifact-root` to scan a
directory and infer artifact roles automatically.

```bash
uv run omf import-run codex \
  --log /private/tmp/codex-run.log \
  --goal "capture external agent run" \
  --diff /private/tmp/change.diff \
  --test-result /private/tmp/pytest.txt \
  --artifact-root /private/tmp/codex-artifacts \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

### `omf capability export`

Export a canonical capability package into a target runtime/model portability
bundle.

```bash
uv run omf capability export repo_issue_triage \
  --target hermes \
  --target-model qwen3.6-27b \
  --source-project source-repo \
  --target-project target-repo \
  --out /private/tmp/repo_issue_triage-hermes-qwen36 \
  --capabilities-dir /private/tmp/omf-capabilities-smoke
```

The export writes `portability.yaml`, source runtime metadata, evidence links,
instructions, context policy, harness metadata, and a target runtime directory.

### `omf capability import`

Import a portability bundle into a target project capability directory and write
a target-side validation report.

```bash
uv run omf capability import /private/tmp/repo_issue_triage-hermes-qwen36 \
  --runtime hermes \
  --model qwen3.6-27b \
  --project target-repo \
  --available-tool shell \
  --validate \
  --capabilities-dir /private/tmp/target-omf-capabilities
```

The import report records whether tool compatibility is `pass`, `partial`, or
`unknown`, whether context remapping is required, and the eval set to run before
marking the target package validated.

### `omf verify`

Verify artifact integrity links and capability source-evidence lineage.

```bash
uv run omf verify capability repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke
```

### `omf registry`

List capability registry information, optionally filtered to one capability.
Entries include eval count, latest eval status, pass rate, runtime profiles,
source evidence count, patch count, promotion metrics, and integrity status.

```bash
uv run omf registry \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --eval-dir /private/tmp/omf-evals-smoke

uv run omf registry repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```

### `omf reflect`

Build a reflection report from capability evidence and optional eval results.

```bash
uv run omf reflect repo_issue_triage \
  --eval-id <eval_id> \
  --note "operator saw repeated issue" \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --eval-dir /private/tmp/omf-evals-smoke \
  --reflection-dir /private/tmp/omf-reflections-smoke
```

### `omf run` Advanced

Run the local OMF artifact pipeline: capture, promote, context pack, replay,
evaluate, and learn. This command processes artifacts; it does not replace the
external agent runtime that performs the original task.

Important options:

- `--goal`, `--name`, `--description`: Required workflow and capability fields.
- File capture options match `omf capture`.
- Harness options match `omf eval`.
- `--allow-failed-capture`: Continue the workflow even when capture fails.
- `--skip-replay-execute`: Build replay records without executing commands.
- `--skip-optional-context`: Exclude optional context from context packing.
- Directory options control where each artifact type is written.

```bash
uv run omf run \
  --goal "triage repo issue" \
  --name repo_issue_triage_v2 \
  --description "GitHub issue triage capability" \
  --prompt tests/fixtures/prompt.md \
  --command "printf 'orchestrated smoke ok\n'" \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "operator rubric attached" \
  --rubric-score "quality:4:5:3:usable" \
  --runtime-tool shell \
  --evidence-dir /private/tmp/omf-run-evidence-smoke \
  --capabilities-dir /private/tmp/omf-run-capabilities-smoke \
  --replay-dir /private/tmp/omf-run-replays-smoke \
  --eval-dir /private/tmp/omf-run-evals-smoke \
  --context-dir /private/tmp/omf-run-context-smoke \
  --learning-dir /private/tmp/omf-run-learning-smoke \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

### `omf status` and `omf resume`

Inspect or resume an orchestrated workflow run.

```bash
uv run omf status <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke

uv run omf resume <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

### `omf rollback`

Move a workflow record back to a previous node and mark it for review.

Supported rollback nodes are `observe_capture`, `structure_promote`,
`context_pack`, `execute_replay`, `evaluate_harness`, and `learn_export`.

```bash
uv run omf rollback <run_id> \
  --to-node execute_replay \
  --reason "rerun command with approval" \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```

### `omf dashboard`

Serve a local HTML dashboard and JSON API for workflow state, approval requests,
reviews, evals, suggested console actions, regression case counts, and
capability health. Capability summaries include pass rate, promotion metrics,
patch count, and integrity status. The JSON API is available at `/api/snapshot`.

```bash
uv run omf dashboard \
  --host 127.0.0.1 \
  --port 8765 \
  --workflow-dir /private/tmp/omf-run-workflows-smoke \
  --evidence-dir /private/tmp/omf-run-evidence-smoke \
  --capabilities-dir /private/tmp/omf-run-capabilities-smoke \
  --replay-dir /private/tmp/omf-run-replays-smoke \
  --eval-dir /private/tmp/omf-run-evals-smoke \
  --review-dir /private/tmp/omf-run-reviews-smoke \
  --eval-set-dir /private/tmp/omf-run-eval-sets-smoke \
  --learning-patch-dir /private/tmp/omf-run-learning-patches-smoke
```

For a one-shot JSON snapshot:

```bash
uv run omf dashboard --once \
  --workflow-dir /private/tmp/omf-run-workflows-smoke \
  --evidence-dir /private/tmp/omf-run-evidence-smoke \
  --capabilities-dir /private/tmp/omf-run-capabilities-smoke \
  --replay-dir /private/tmp/omf-run-replays-smoke \
  --eval-dir /private/tmp/omf-run-evals-smoke \
  --review-dir /private/tmp/omf-run-reviews-smoke \
  --eval-set-dir /private/tmp/omf-run-eval-sets-smoke \
  --learning-patch-dir /private/tmp/omf-run-learning-patches-smoke
```

## Example Template

An editable starter capability template is available at
`examples/capability-template.yaml`. It shows the expected `capability.yaml`
shape for field policy, context sources, workflow control, promotion criteria,
patch history, and integrity links.

### `omf inspect`

Inspect an artifact by type and id. Supported target types are `evidence`,
`capability`, `replay`, `eval`, `workflow`, `context`, `learning`, and
`reflection`.

```bash
uv run omf inspect capability repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke
```

### `omf export`

Export a capability and its related evidence, evals, context bundles, learning
exports, and reflection reports. Export requires `--approve-export`.

```bash
uv run omf export repo_issue_triage \
  --approve-export \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --eval-dir /private/tmp/omf-evals-smoke \
  --context-dir /private/tmp/omf-context-smoke \
  --learning-dir /private/tmp/omf-learning-smoke \
  --reflection-dir /private/tmp/omf-reflections-smoke \
  --export-dir /private/tmp/omf-exports-smoke
```

## Practical Notes

- Prefer safe smoke commands first, such as `printf 'smoke ok\n'`.
- Use explicit artifact directories when trying examples so it is easy to find
  or discard generated records.
- Record failed runs too. A failed command, rejected review, or failed checklist
  can become the evidence that improves the next capability.
- Keep human review explicit. User intervention is not treated as a failure; it
  is part of the learning signal.

For the deeper product specification, see `oh-my-field.md`.
