# Security Policy

oh-my-field is currently an alpha CLI. It captures command output, run logs,
test results, and artifacts as evidence, so treat every import and execution
surface as security-sensitive.

## Reporting Issues

Use GitHub Security Advisories for `Baekpica/oh-my-field` when available. If a
private advisory is not available, open a GitHub issue with a minimal
description and do not include secrets, credentials, private logs, or exploit
payloads.

## Command Execution Boundary

OMF is not an arbitrary shell sandbox. It risk-assesses command strings and
blocks risky commands unless `--approve-command-risk` is provided, but approved
commands still run on the local machine.

Commands run with a minimal environment by default. Use `--allow-env NAME` only
when a command requires a specific variable.

## Artifact Import Boundary

`import-run --artifact-root` applies default excludes for `.git/`, `.venv/`,
`node_modules/`, `.env*`, private key patterns, and symlinks. Use `.omfignore`,
`--exclude`, `--max-artifact-count`, and `--max-total-artifact-bytes` before
importing broad directories.

## Secret Redaction Limits

`--redact-secrets` covers common key/value secrets, bearer tokens, and AWS access
key patterns. It is not a formal DLP system. Prefer excluding sensitive files
before import rather than relying on redaction after capture.
