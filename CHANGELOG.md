# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Added public release CI gates for lint, format, type checking, tests, build,
  and distribution smoke tests.
- Split imported-run capture quality from task outcome in promotion metrics.
- Hardened shell command execution records with minimal environment handling.
- Added shell-free `--run-argv` execution and `--require-cwd-inside-project`
  containment to `omf capability validate`; execution records now report the
  shell mode used.
- Added artifact root import excludes, `.omfignore`, and traversal limits.
- Added public onboarding, security, contribution, and release documentation.

## 0.1.0

- Initial alpha CLI for capturing evidence, promoting capabilities, replaying
  checks, evaluating results, exporting runtime assets, and inspecting local
  workflow state.
