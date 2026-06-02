# Local Capability Lifecycle

This use case covers the implemented `omf` CLI lifecycle. It does not claim a result until the
command has actually run and written evidence.

## Goal

Turn a real shell command execution into a replayable capability:

1. `omf capture` runs a shell command and records command output plus artifact hashes.
   Optional `--check` commands run as real harness checks.
2. `omf promote` accepts only passing evidence and writes a capability manifest with the source evidence SHA-256.
3. `omf replay` reruns the manifest command and verifies artifact hashes while recording manifest and replay evidence SHA-256 values.
4. `omf eval` repeats replay and records verified replay results, pass rate, and measured command/harness timing.
5. `omf list` and `omf inspect` make the generated JSON artifacts inspectable and validated.
6. `omf review` records a reviewer decision against a validated JSON artifact.
7. `omf regress` creates a regression case from a manifest plus source artifact and immediately runs replay.
8. `omf learn` exports inspected artifacts into a local JSONL learning candidate set.
9. `omf search` finds the generated JSON artifacts by reading local store files and validating
   matching artifacts with `omf inspect`.

## Minimal Run

Create a script that writes an artifact.

```bash
mkdir -p /tmp/omf-lifecycle
cat > /tmp/omf-lifecycle/make_artifact.py <<'PY'
from pathlib import Path

Path("artifact.txt").write_text("verified artifact", encoding="utf-8")
PY
```

Create a harness check that validates the artifact content.

```bash
cat > /tmp/omf-lifecycle/check_artifact.py <<'PY'
from pathlib import Path

actual = Path("artifact.txt").read_text(encoding="utf-8")
raise SystemExit(0 if actual == "verified artifact" else 2)
PY
```

Capture the actual run.

```bash
omf capture \
  --goal "prove artifact generation" \
  --command "python /tmp/omf-lifecycle/make_artifact.py" \
  --artifact artifact.txt \
  --check "python /tmp/omf-lifecycle/check_artifact.py" \
  --cwd /tmp/omf-lifecycle \
  --store-dir /tmp/omf-lifecycle/.omf
```

The command is executed through the local shell, so shell syntax such as redirection is part of the
actual run instead of a displayed sample. The command writes `.omf/evidence/<run-id>.json`. That
file contains the executed command, shell invocation args, exit code, stdout, stderr, duration,
runtime information, artifact existence, artifact size, and artifact SHA-256. It also contains
every harness command result. If any `--check` command fails, the evidence status is `fail`.

When capture runs inside a Git repository, evidence also includes repository root, HEAD SHA,
current branch, changed files, dirty state, and a SHA-256 digest of staged plus unstaged diff
content. These fields are measured from the local repository at capture time.

Promote only the passing evidence.

```bash
omf promote /tmp/omf-lifecycle/.omf/evidence/<run-id>.json \
  --name "artifact lifecycle" \
  --store-dir /tmp/omf-lifecycle/.omf
```

The command writes `.omf/capabilities/artifact-lifecycle/manifest.json`. The manifest stores the
source evidence path and SHA-256, so later inspection can detect source evidence changes.

Replay the capability.

```bash
omf replay /tmp/omf-lifecycle/.omf/capabilities/artifact-lifecycle/manifest.json \
  --store-dir /tmp/omf-lifecycle/.omf
```

Replay first verifies that the capability manifest passes `omf inspect`, including source evidence
SHA-256 and promoted contract checks. It passes only if the command exit code is still successful,
the artifact hash matches the promoted evidence, and every promoted harness command passes again.
The replay artifact stores the capability manifest path/SHA-256 and replay evidence path/SHA-256.
`omf inspect` recomputes replay checks and timing from those linked files instead of trusting the
stored replay labels.

Evaluate the capability.

```bash
omf eval /tmp/omf-lifecycle/.omf/capabilities/artifact-lifecycle/manifest.json \
  --runs 2 \
  --store-dir /tmp/omf-lifecycle/.omf
```

Eval first verifies that the capability manifest passes `omf inspect`. The eval artifact records
the actual replay results, pass rate, and measured timing summary. Timing comes from the real
command and harness command durations recorded during replay. If any replay fails, eval fails.
`omf inspect` validates the embedded replay results and recomputes pass count, pass rate, status,
and timing before treating the eval as valid.

Record a review against the eval artifact.

```bash
omf review /tmp/omf-lifecycle/.omf/evals/<eval-id>.json \
  --reviewer qa-reviewer \
  --decision approve \
  --note "approved after real replay and eval artifacts passed" \
  --store-dir /tmp/omf-lifecycle/.omf
```

The review artifact stores the reviewer, decision, note, reviewed artifact path, reviewed artifact
SHA-256, artifact type, and artifact status. It fails if the reviewed JSON artifact is unsupported
or if the decision is outside the implemented review decision set. `omf inspect` reopens the
reviewed artifact and rejects the review if the reviewed artifact hash, type, or status no longer
matches the review record.

Create and run a regression case from the review artifact.

```bash
omf regress /tmp/omf-lifecycle/.omf/capabilities/artifact-lifecycle/manifest.json \
  --source-artifact /tmp/omf-lifecycle/.omf/reviews/<review-id>.json \
  --name "artifact lifecycle regression" \
  --reason "review requested a regression case from a verified eval artifact" \
  --store-dir /tmp/omf-lifecycle/.omf
```

Regression first verifies both the source artifact and capability manifest with `omf inspect`. The
regression artifact stores the source artifact path and SHA-256, manifest path and SHA-256, reason,
capability name, and replay result. It is not a paper label; the command reruns the capability
before writing the regression case. Invalid manifests fail before any replay or regression JSON is
written. `omf inspect` reopens the source artifact and capability manifest, verifies both SHA-256
values, and rejects the regression case if its stored links no longer match inspected artifacts.

Export learning candidates from real artifacts.

```bash
omf learn \
  --source-artifact /tmp/omf-lifecycle/.omf/evals/<eval-id>.json \
  --source-artifact /tmp/omf-lifecycle/.omf/reviews/<review-id>.json \
  --source-artifact /tmp/omf-lifecycle/.omf/regressions/<regression-id>.json \
  --name "artifact lifecycle learning" \
  --purpose prompt_improvement \
  --note "exported from verified lifecycle artifacts" \
  --store-dir /tmp/omf-lifecycle/.omf
```

The learning export writes `.omf/learning/<export-name>-<export-id>/items.jsonl` and a
`manifest.json` that records the JSONL path, JSONL SHA-256, item count, source artifact paths,
source artifact SHA-256 values, source artifact types, and source artifact statuses. This is a
local export for prompt improvement, eval-set assembly, or fine-tuning candidate review. It is not an actual model training run, upload, or fine-tuning job.
`omf inspect` reopens the JSONL file, verifies its SHA-256, validates each JSONL row, and rejects
the learning export if the row count or row contents no longer match the manifest. It also reopens
each source artifact and rejects the export if any source artifact hash, type, or status no longer
matches the exported item.

List generated artifacts.

```bash
omf list --store-dir /tmp/omf-lifecycle/.omf
```

List validates every discovered store entry with `omf inspect` and returns each artifact kind,
path, name, status, and `validated: true`. If any discovered JSON artifact is corrupted or
stored under the wrong kind bucket, list fails instead of presenting it as a valid store artifact.

Inspect an artifact.

```bash
omf inspect /tmp/omf-lifecycle/.omf/capabilities/artifact-lifecycle/manifest.json
```

Inspect validates the JSON schema and returns a short summary. Evidence inspection recomputes the
command/harness status and verifies recorded artifact existence, SHA-256, and size. Capability
inspection also verifies that the source evidence file still exists, still matches the recorded
SHA-256, is passing, and matches the promoted command/artifact/check contract. Replay inspection
verifies the linked manifest and replay evidence hashes, then recomputes checks and timing. Eval
inspection validates its embedded replay results. Review, regression, and learning inspection
verify their linked artifact hashes instead of trusting the stored label. Unsupported or corrupted
artifact schemas fail instead of being treated as valid results.

Search the local store artifacts.

```bash
omf search "prove artifact generation" --store-dir /tmp/omf-lifecycle/.omf
```

Restrict search to capability manifests.

```bash
omf search "artifact-lifecycle" \
  --kind capability \
  --store-dir /tmp/omf-lifecycle/.omf
```

Search reads the actual JSON files under the store and returns matching paths, artifact kinds,
statuses, validation flags, scores, and snippets. A matched artifact must pass `omf inspect` before
it is returned. Search fails instead of returning a corrupted artifact or an artifact stored in the
wrong kind bucket. It does not claim semantic retrieval or external registry lookup.

## Release Rule

Do not document a capability as working unless `capture`, `promote`, `replay`, and any claimed
`eval` result have produced JSON artifacts that can be found with `list` and validated with
`inspect`; list entries must also have `validated: true`. Evidence claims require status
recalculation plus recorded artifact hash verification. Capability claims require a passing `inspect` result with source evidence hash verification
plus a passing `replay`. Replay claims require manifest/evidence hash verification
from `inspect` and a replay command that accepted only an inspected capability manifest. Eval claims require embedded replay verification from `inspect`. If latency or
timing is claimed, it must come from the replay/eval timing fields. If human review is claimed, it
must come from a `review` artifact whose `inspect` result verifies the reviewed artifact hash. If
discoverability is claimed, the artifact must also be returned by `search` with `validated: true`.
If regression coverage is claimed, it must come from a `regression` artifact with an embedded
replay result and an `inspect` result that verifies the source artifact and manifest hashes. If
learning export is claimed, it must come from a `learning` manifest with a hashed JSONL file,
inspected source artifact hashes, and a passing `inspect` result that verifies the JSONL content
and the source artifact hashes.
