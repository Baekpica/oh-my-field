# Security

OMF captures evidence from local work. That evidence can include logs, command
outputs, diffs, tests, and artifacts, so security controls focus on avoiding
accidental execution and accidental capture.

## Command Execution

OMF is not an arbitrary shell runner. Commands are captured and risk-assessed as
evidence, and risky commands are recorded but not executed unless
`--approve-command-risk` is provided.

There are two execution forms:

- **argv (preferred)**: `--run-argv` runs a command without a shell, so shell
  metacharacters (`>`, `|`, `;`, `$()`) are literal arguments and there is no
  shell-injection surface. Pass one token per flag, e.g.
  `--run-argv pytest --run-argv -q`.
- **shell string (legacy)**: `--command`, `--harness-command`, and
  `--run-command` are shell execution surfaces. They run through the shell, so
  treat their contents as code.

`--run-command` and `--run-argv` are mutually exclusive. OMF records cwd, shell
mode (`shell: true|false`), risk categories, approval state, and environment
policy in each execution record.

Commands run with a minimal environment by default (`PATH`, `HOME`, `TMPDIR`);
known secret-bearing variables are stripped and recorded as blocked. Use
`--allow-env NAME` only when a command needs that variable.

`--require-cwd-inside-project` blocks execution (recording it, not running it)
when the resolved working directory escapes the project root. The working
directory is resolved through symlinks before the check.

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
  --max-total-artifact-bytes 52428800
```

Secret redaction is on by default: imported text is scanned for key/value
secrets, bearer tokens, AWS access keys, GitHub and Slack tokens, JWTs, and
private-key blocks, and matches are replaced with `[REDACTED]`. Pass
`--no-redact-secrets` to keep raw content. Prefer excluding sensitive files
before import. Redaction is a backup control, not a guarantee.
