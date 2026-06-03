# Security

OMF captures evidence from local work. That evidence can include logs, command
outputs, diffs, tests, and artifacts, so security controls focus on avoiding
accidental execution and accidental capture.

## Command Execution

Commands are risk-assessed before execution. Risky commands are recorded but not
executed unless `--approve-command-risk` is provided.

Command strings are shell strings. Treat `--command`, `--harness-command`, and
`--run-command` as shell execution surfaces. OMF records cwd, shell mode, risk
categories, approval state, and environment policy in each execution record.

Commands run with a minimal environment by default. Use `--allow-env NAME` only
when a command needs that variable.

## Artifact Import

`import-run --artifact-root` skips common sensitive or oversized paths by
default, including `.git/`, `.venv/`, `node_modules/`, `.env*`, private key
patterns, build outputs, archives, databases, and symlinks.

Use these controls for broad imports:

```bash
omf import-run codex \
  --log ./agent.log \
  --goal "capture run" \
  --artifact-root . \
  --exclude "secrets/**" \
  --max-artifact-count 200 \
  --max-total-artifact-bytes 52428800 \
  --redact-secrets
```

Prefer excluding sensitive files before import. Redaction is a backup control,
not a guarantee.
