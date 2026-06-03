# Release

Public release is tag-driven.

1. Verify local gates.
2. Build wheel and sdist.
3. Smoke test both artifacts with isolated `omf --help`.
4. Publish with PyPI Trusted Publishing from the release workflow.
5. Upload GitHub release artifacts and checksums.

Example alpha tag:

```bash
git tag v0.1.0a1
git push origin v0.1.0a1
```

PyPI/TestPyPI publishing requires configuring the matching GitHub environment
and trusted publisher in PyPI before pushing a tag.
