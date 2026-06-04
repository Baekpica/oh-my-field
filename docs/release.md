# Release

Public release is tag-driven.

1. Verify local gates.
2. Build wheel and sdist.
3. Smoke test both artifacts with isolated `omf --help`, `omf doctor --json`,
   `omf install skill`, and `omf install mcp`.
4. Publish with PyPI Trusted Publishing from the release workflow.
5. Upload GitHub release artifacts and checksums.

Local release smoke:

```bash
uv build
uv run --isolated --no-project --with dist/*.whl omf install skill --runtime generic --out /tmp/omf-wheel-skill
uv run --isolated --no-project --with dist/*.whl omf install mcp --client generic --out /tmp/omf-wheel-mcp.json
uv run --isolated --no-project --with dist/*.whl omf doctor --json
```

User-facing install path:

```bash
pipx install oh-my-field
omf install skill --runtime codex
omf install mcp --client generic --out .omf/mcp.json
```

Trial path:

```bash
uvx oh-my-field --help
```

First agent prompt:

```text
/omf
track this task with OMF
```

Example alpha tag:

```bash
git tag v0.1.0a1
git push origin v0.1.0a1
```

PyPI/TestPyPI publishing requires configuring the matching GitHub environment
and trusted publisher in PyPI before pushing a tag.
