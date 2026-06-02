# oh-my-field
Field-fit agents to real work. Turn tacit know-how into reusable capabilities.

## CLI

`omf` provides a local evidence-first lifecycle:

- `omf capture` executes a real shell command and stores evidence JSON.
- `omf capture --check` runs real harness commands and fails the evidence if any check fails.
- `omf capture` records local Git root, HEAD, branch, changed files, and diff hash when run inside a Git repository.
- `omf promote` turns passing evidence into a capability manifest and records the source evidence SHA-256.
- `omf replay` reruns only an inspected capability manifest and stores manifest/evidence SHA-256 checks.
- `omf eval` repeats replay from an inspected capability manifest and writes an eval artifact with verified replay results, pass rate, and measured timing.
- `omf list` lists local artifacts only after validating each entry with `omf inspect`.
- `omf inspect` validates and summarizes a single omf JSON artifact, including evidence artifact hashes, linked evidence, and JSONL hash checks where applicable.
- `omf review` records a reviewer decision against an inspected omf JSON artifact.
- `omf regress` creates and immediately runs a regression case from an inspected capability manifest and source artifact.
- `omf learn` exports inspected artifacts into a local JSONL learning candidate set with a hashed manifest.
- `omf search` searches local store JSON artifacts and returns only matching artifacts validated by `omf inspect`.

## Evidence Integrity

Do not ship or document a feature as working unless it actually ran and produced evidence. Unsupported GPU, CPU, cost, timing, performance, or improvement claims must be omitted or explicitly marked as not measured.

## Example Packs

- [Computing resource workflow](docs/use-cases/computing-resource-workflow.md)
- [Local capability lifecycle](docs/use-cases/local-cli-lifecycle.md)
