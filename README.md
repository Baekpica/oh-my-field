<p align="center">
  <img src="assets/oh-my-field-logo.png" alt="oh-my-field logo" width="760">
</p>

# oh-my-field

[![CI](https://github.com/Baekpica/oh-my-field/actions/workflows/ci.yml/badge.svg)](https://github.com/Baekpica/oh-my-field/actions/workflows/ci.yml)

[Website](https://oh-my-field.dev/)

Field-fit agents to real work. oh-my-field turns one-off agent sessions into
portable, evidence-backed capability packages.

OMF can be driven by hand from the CLI, but the intended loop is **agent-assisted**:
an agent records its own work as an OMF session, materializes that work into
immutable evidence, promotes the repeatable parts into a reviewable capability
package, and carries that capability across runtimes, models, and projects.

The OMF CLI is Apache-2.0 licensed. Capability artifacts generated from your
work remain owned by you or the project that generated them unless you choose to
publish them under separate terms.

oh-my-field is currently published as an alpha CLI. The core package and
capability contracts are usable, but release consumers should expect the public
surface to keep tightening while feedback lands.

## What OMF Is

- A capability **packaging and verification layer** around external agents.
- A way to keep good agent work as reviewable, repeatable, portable packages.

## What OMF Is Not

- Not an agent runtime — Codex, Claude Code, Hermes, Pi, Odysseus, or another agent does the work.
- Not a prompt vault — a capability is instructions plus context policy, harness,
  evidence, eval cases, and integrity metadata.
- Not an autonomous shell runner — risky commands are recorded as intent and
  require explicit approval before they execute.

## Why It Exists

- Agent work disappears into chat history instead of compounding.
- A good run is hard to reproduce without its evidence, context, and checks.
- Local/domain tacit knowledge (constraints, preferences, failure history) is
  rarely captured.
- Migrating runtime or model silently loses behavior.
- Teams need evidence, harnesses, and reviewable packages — not another
  hand-written prompt.

The product goal: turn "the agent did this once" into "this team can reuse and
verify this capability again."

## How OMF Fits Into An Agent Workflow

The agent still does the work. OMF records what happened, preserves evidence,
promotes repeatable work into a capability package, and tracks whether that
capability actually works on another runtime or project.

```text
external agent runtime
  Codex / Claude Code / Hermes / Pi / Odysseus / local agent
        │
        ▼
OMF session  ──or──  imported run
        │
        ▼
evidence record
        │
        ▼
capability package
        │
        ├── health / verify / eval / review
        ├── learn / reflect / harden
        ▼
runtime export bundle
        │
        ▼
target project import
        │
        ▼
target validation
```

See [docs/concepts.md](docs/concepts.md) for the `Field`, `Evidence`,
`Capability`, `Harness`, and `Portability` definitions, and
[docs/agent-ux.md](docs/agent-ux.md) for the activation model.

## Install

```bash
pipx install oh-my-field      # persistent CLI install
omf --help

uvx oh-my-field --help        # try without installing
```

Development install from source:

```bash
git clone https://github.com/Baekpica/oh-my-field.git
cd oh-my-field
uv sync --all-extras --dev
uv run omf --help
```

Local checks mirror CI — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/development.md](docs/development.md). The full install guide, including how
to verify the install, is in [docs/install.md](docs/install.md).

## Agent Activation

OMF can be used manually, but the intended loop is agent-assisted. Install an OMF
meta-skill for the target agent runtime:

```bash
omf install skill --runtime codex
omf install skill --runtime claude_code
omf install skill --runtime hermes
omf install skill --runtime pi
omf install skill --runtime odysseus --project /path/to/odysseus
omf install skill --runtime generic --scope export
```

By default Codex, Claude Code, Hermes, and Pi install into their user-level
skill discovery paths (`~/.agents/skills`, `~/.claude/skills`,
`~/.hermes/skills`, `~/.pi/agent/skills`). Odysseus installs into the target
checkout's `data/skills` tree. `generic` keeps producing reviewable export
assets under `.omf/agent/omf-skill`.

For MCP-capable clients, patch the matching client config and run the stdio
server:

```bash
omf install mcp --client codex
omf install mcp --client claude_code
omf install mcp --client hermes
omf install mcp --client pi
omf install mcp --client odysseus --project /path/to/odysseus
omf install mcp --client generic --scope export --out .omf/mcp.json
omf mcp serve
```

Once activated, a human can say `/omf` or "track this task with OMF" and the
agent records its work as an OMF session, materializes that session into
immutable evidence, and proposes a reusable capability package. The MCP surface
mirrors the same loop (`omf_start_session`, `omf_record_input`,
`omf_record_artifact`, `omf_record_validation`, `omf_record_decision`,
`omf_materialize_session`, `omf_promote_capability`, …). See
[docs/mcp.md](docs/mcp.md) and [docs/agent-ux.md](docs/agent-ux.md).

## Quickstart A: Track An Agent Session

Use this when an agent can call OMF *during* the work.

```bash
omf init

omf session start \
  --runtime codex \
  --model gpt-5.5 \
  --goal "triage repository issue" \
  --activation-source skill
```

Create a tiny input, output artifact, and validation result for the example:

```bash
mkdir -p output
printf "issue: repository bug report\n" > issue.md
printf '{"status":"triaged"}\n' > output/report.json
printf "pytest passed\n" > output/pytest.txt
```

Copy the `session_id` from the JSON output, then record meaningful events. The
context, artifact, and validation paths make the materialized evidence
strict-ready for promotion:

```bash
omf session event <session_id> \
  --type context \
  --summary "Captured issue report" \
  --path issue.md

omf session event <session_id> \
  --type command \
  --summary "Ran the test suite" \
  --command "uv run pytest" \
  --exit-code 0

omf session event <session_id> \
  --type artifact \
  --summary "Produced triage report" \
  --path output/report.json

omf session event <session_id> \
  --type test_result \
  --summary "pytest passed" \
  --path output/pytest.txt \
  --command "uv run pytest" \
  --exit-code 0

omf session finish <session_id> --outcome success
omf session materialize <session_id>
omf session suggest-capability <session_id>
```

Promote the resulting evidence into a capability and check its health. `promote`
is strict by default; use `--no-strict` only when intentionally promoting legacy
or incomplete evidence:

```bash
omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "Repository issue triage capability"

omf health repo_issue_triage
```

## Quickstart B: Import An Existing Run

Use this when the agent already produced logs, diffs, test outputs, or artifacts.

```bash
mkdir -p /tmp/omf-smoke
printf "agent run log\n" > /tmp/omf-smoke/codex.log
printf "pytest passed\n" > /tmp/omf-smoke/pytest.txt

omf import-run codex \
  --log /tmp/omf-smoke/codex.log \
  --goal "triage repo issue" \
  --test-result /tmp/omf-smoke/pytest.txt \
  --evidence-dir /tmp/omf-smoke/evidence \
  --outcome success

omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "Repository issue triage capability" \
  --evidence-dir /tmp/omf-smoke/evidence \
  --capabilities-dir /tmp/omf-smoke/capabilities

omf health repo_issue_triage \
  --capabilities-dir /tmp/omf-smoke/capabilities
```

From a source checkout, prefix each command with `uv run`. The full walkthrough,
including the export/import/validate path, lives in
[docs/quickstart.md](docs/quickstart.md).

## What You Get

`promote` creates a runtime-neutral package under `capabilities/<name>/` — **the
source of truth**:

```text
capabilities/<name>/
  capability.yaml     # canonical metadata and provenance
  instructions.md     # runtime-neutral agent instructions
  harness.yaml        # verification and approval boundaries
  README.md           # human-readable capability card
  contracts/
    task_contract.yaml
    artifacts.yaml
    validation.md
    replay_plan.yaml
  validators/
    validate_contract.py
```

The contract bundle is generated from hardened evidence and is copied into
runtime exports so target agents can see the task, artifact, validation, and
replay contract without reconstructing it from prose.

That per-capability `README.md` is the capability *card* — purpose, source
evidence, harness summary, portability and review status — and is distinct from
this repository's README.

`omf init` sets up the repo-local field — `.omf/config.yaml`, `.omfignore`, and
the artifact directories. It also creates the top-level `capabilities/`
directory for reviewable packages:

```text
capabilities/
  <name>/

.omf/
  evidence/      sessions/     exports/      imports/
  evals/         replays/      context/      learning/
  datasets/      reflections/  workflows/    runs/
```

Runtime-specific files (Codex instructions, Claude Code memory,
Hermes/Pi/Odysseus skill projections, and generic skill bundles) are
**projections** of the package, not the source of truth.

`.omf/config.yaml` records local field defaults and `.omf/registry.yaml` is local
registry metadata. The package files under `capabilities/<name>/` remain the
authoritative capability source.

## Learning And Datasets

Accumulated evidence becomes reviewable learning material, not silent training
data. `learn` and `reflect` turn evidence and eval results into learning exports
and reflection reports; `learn-patch` records accept/reject decisions on proposed
prompt patches.

`dataset-export` then emits JSONL from those downstream artifacts — learning
exports (fine-tuning), patch decisions (preference), and eval results (eval) —
not from raw evidence. Review and harness status sit upstream, so unreviewed or
failing runs do not silently become a dataset.

```bash
omf dataset-export <capability_name> --dataset-type all
```

## Command Map

| Area | Commands | Purpose |
| --- | --- | --- |
| Setup | `init`, `doctor`, `version` | Create and inspect a repo-local OMF field |
| Agent activation | `install skill`, `install mcp`, `mcp serve` | Give agents a lower-friction OMF surface |
| Session tracking | `session start`, `session event`, `session finish`, `session materialize`, `session suggest-capability` | Record active agent work as structured evidence |
| Evidence ingestion | `import-run`, `capture` | Import existing logs, artifacts, diffs, and test results |
| Capability build | `promote`, `health`, `harden`, `card`, `registry` | Create and inspect reusable capability packages |
| Verification | `replay`, `eval`, `verify`, `regression-case` | Check whether a capability still satisfies its harness |
| Review and learning | `review`, `approve`, `reject`, `revise`, `learn`, `learn-patch`, `reflect` | Turn feedback and failures into accepted patches |
| Pipeline | `run`, `resume`, `rollback`, `status` | Drive and resume the full checkpointed pipeline |
| Portability | `capability export`, `capability import`, `capability validate`, `capability remap`, `capability adapt`, `export` | Move capabilities across runtimes and projects |
| Operations | `dashboard`, `inspect`, `diff`, `explain` (`why`), `context`, `dataset-export` | Inspect, explain, compare, and export accumulated evidence |

## Portability Lifecycle

A capability moves across runtimes through four **distinct** states — keep them
separate, because "can be exported" is not "works on the target":

- **Exported**: converted into a target runtime bundle (`omf capability export`).
- **Imported**: bundle materialized in a target project (`omf capability import`).
- **Validated**: an actual target run passed under the recorded target
  runtime/model/project (`omf capability validate --run-command ...`). Static
  `import --validate` alone leaves the import at `needs_validation`.
- **Portable**: the capability has at least one validated target import.

`omf health` reports `export_status`, `import_status`, and `validation_status`
separately, and lists each imported target with its own status.

```bash
omf capability export repo_issue_triage --target hermes \
  --out .omf/exports/repo_issue_triage-hermes
omf capability import .omf/exports/repo_issue_triage-hermes \
  --runtime hermes --validate
omf capability validate repo_issue_triage --target hermes \
  --run-command "hermes-code --profile target --skill repo_issue_triage" \
  --approve-command-risk
```

The full cross-runtime walkthrough (Codex/gpt-5.5 → Hermes/qwen3.6-27B, redacted
evidence transfer, overlays) is in [docs/portability.md](docs/portability.md)
and the [runtime adapter docs](docs/runtime-adapters/).

## Safety Model

OMF is not an arbitrary shell runner. It records command intent and risk.
Commands classified as write, destructive, external, credential, production, or
paid risk are recorded but **not executed** unless they receive explicit
approval (`--approve-command-risk`). Capability exports are gated by
`--approve-export`.

- Prefer the shell-free `--run-argv` form (one token per flag) over the legacy
  shell strings `--command` / `--harness-command` / `--run-command`;
  `--require-cwd-inside-project` blocks commands that escape the project root.
- Commands run with a minimal environment (`PATH`, `HOME`, `TMPDIR`);
  secret-bearing vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_*`,
  `GITHUB_TOKEN`, …) are stripped and recorded. Opt one back in with
  `--allow-env NAME`.
- `import-run --artifact-root` skips `.git/`, `.venv/`, `node_modules/`, `.env*`,
  private-key patterns, and symlinks; honors `.omfignore`/`--exclude`; and caps
  traversal via `--max-artifact-count`/`--max-total-artifact-bytes`.

Full details: [docs/security.md](docs/security.md).

## Architecture At A Glance

OMF is organized into layers (flat root modules such as `oh_my_field.models` and
`oh_my_field.storage` remain as compatibility shims while call sites migrate):

| Layer | Path | Responsibility |
| --- | --- | --- |
| CLI | `src/oh_my_field/cli/` | Typer command surface |
| Application | `src/oh_my_field/application/` | use-case workflows |
| Domain | `src/oh_my_field/domain/` | models, rules, lifecycle |
| Infrastructure | `src/oh_my_field/infrastructure/` | storage, hashing, execution |
| Adapters | `src/oh_my_field/adapters/` | runtime-specific behavior |
| Schemas | `schemas/` | artifact JSON Schema contracts |

See [docs/architecture/overview.md](docs/architecture/overview.md) for the
dependency direction and per-concept layout.

## Learn More

- Full product and feature reference: [oh-my-field.md](oh-my-field.md)
- Install guide: [docs/install.md](docs/install.md)
- Quickstart (session / import / portability paths): [docs/quickstart.md](docs/quickstart.md)
- Agent UX and activation: [docs/agent-ux.md](docs/agent-ux.md)
- MCP surface: [docs/mcp.md](docs/mcp.md)
- Concepts: [docs/concepts.md](docs/concepts.md)
- Portability: [docs/portability.md](docs/portability.md)
- Security model: [docs/security.md](docs/security.md)
- Architecture overview: [docs/architecture/overview.md](docs/architecture/overview.md)
- Development guide: [docs/development.md](docs/development.md)
- Runtime adapters:
  [Codex](docs/runtime-adapters/codex.md),
  [Claude Code](docs/runtime-adapters/claude-code.md),
  [Hermes](docs/runtime-adapters/hermes.md),
  [Generic](docs/runtime-adapters/generic.md)

## Practical Notes

- The agent-assisted session loop is the primary path; manual `import-run` is the
  fallback when you only have logs after the fact.
- Keep generated examples in `/private/tmp/...` while trying the CLI.
- Record failed runs too; they are the raw material for stronger capabilities.
- Treat human review as part of the system, not as a failure mode.
