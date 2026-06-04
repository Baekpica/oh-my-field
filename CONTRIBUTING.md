# Contributing

oh-my-field is in alpha. Keep changes small, evidence-backed, and easy to
verify.

## Development Setup And Checks

See the [development guide](docs/development.md) for setup, the strict
test/lint/type-check gates, the layered architecture and compatibility-shim
rules, and the project conventions. The short version:

```bash
uv sync --all-extras --dev
uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest && uv build
```

## Contribution Workflow

1. Keep each change focused on one behavior or document surface.
2. Add tests for behavior changes before calling the work done.
3. Avoid committing generated evidence, local `.omf/` audit data, secrets, or
   build artifacts.
4. Document command execution, artifact import, or portability behavior changes
   in README or `docs/`.

Security issues should follow [SECURITY.md](SECURITY.md).
