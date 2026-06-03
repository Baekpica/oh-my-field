# CI

The release quality gate mirrors the local commands:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run omf version --json
uv run omf doctor --json
uv build
uv run --isolated --no-project --with dist/*.whl omf --help
uv run --isolated --no-project --with dist/*.tar.gz omf --help
```

GitHub Actions runs the quality gate on pull requests and pushes to `main`, then
builds and smoke-tests wheel and sdist artifacts.
