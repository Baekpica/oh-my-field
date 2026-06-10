# Release

Public release is tag-driven. The release target for this branch is `v0.2.2`.
Use `0.2.2` for the patch release that turns on import secret redaction by
default, adds the `privilege_escalation` command risk category, and brings the
Hermes runtime export to parity with the other targets.

Tag only after the release commit has merged to `main` and the local gates below
pass from a clean checkout.

1. Verify local gates.
2. Build wheel and sdist.
3. Smoke test both artifacts with isolated `omf --help`, `omf doctor --json`,
   `omf install skill`, `omf install mcp`, a `pipx` wheel install, and the default
   `omf init -> import-run -> promote -> health -> export` flow.
4. Publish with PyPI Trusted Publishing from the release workflow.
5. Upload GitHub release artifacts and checksums.

Publishing uses GitHub OIDC through PyPI Trusted Publishing. Do not add PyPI API
tokens to this repository unless the OIDC path is intentionally retired.

Local release smoke:

```bash
version=0.2.2
uv build
uv run --isolated --no-project --with dist/*.whl omf install skill --runtime generic --scope export --out /tmp/omf-wheel-skill
uv run --isolated --no-project --with dist/*.whl omf install mcp --client generic --scope export --out /tmp/omf-wheel-mcp.json
uv run --isolated --no-project --with dist/*.whl omf doctor --json
pipx_root="$(mktemp -d)"
mkdir -p "$pipx_root/home" "$pipx_root/bin"
PIPX_HOME="$pipx_root/home" PIPX_BIN_DIR="$pipx_root/bin" pipx install "dist/oh_my_field-${version}-py3-none-any.whl"
PATH="$pipx_root/bin:$PATH" omf doctor --json
bash scripts/smoke-default-flow.sh "dist/oh_my_field-${version}-py3-none-any.whl"
bash scripts/smoke-default-flow.sh "dist/oh_my_field-${version}.tar.gz"
```

Public visibility timing:

Switch the GitHub repository from private to public after the GitHub environments
and PyPI/TestPyPI trusted publishers are configured, and after the final scrub
passes. Do this before pushing the release tag so release links, GitHub Release
assets, and PyPI metadata point at public pages from the first public publish.

Repository scrub before making a release public:

```bash
git grep -nE 'API_KEY|SECRET|TOKEN|PASSWORD|BEGIN .*PRIVATE KEY' -- ':!uv.lock'
git grep -nE 'gha-creds|pypirc|\.env' -- ':!uv.lock'
git status --ignored --short
```

Review expected matches in tests, docs, and safety allow/block lists. There
should be no committed local `.omf/` state, generated credentials, or private
run artifacts.

User-facing install path:

```bash
pipx install oh-my-field
omf install skill --runtime codex
omf install mcp --client codex
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

Trusted publisher setup:

| Index | Project | Owner | Repository | Workflow | Environment |
| --- | --- | --- | --- | --- | --- |
| TestPyPI | `oh-my-field` | `Baekpica` | `oh-my-field` | `release.yml` | `testpypi` |
| PyPI | `oh-my-field` | `Baekpica` | `oh-my-field` | `release.yml` | `pypi` |

The matching GitHub environments must exist before publishing. Keep `testpypi`
unprotected for preflight publishing. Protect `pypi` with a required reviewer
once GitHub environment protection is available for the repository visibility/plan.

0.2.2 release tag:

```bash
git checkout main
git pull --ff-only
version=0.2.2
git tag "v${version}"
git push origin "v${version}"
```

PyPI/TestPyPI publishing requires configuring the matching GitHub environment
and trusted publisher in PyPI before pushing a tag.
