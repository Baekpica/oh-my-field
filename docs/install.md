# Install

## Persistent CLI Install

```bash
pipx install oh-my-field
omf --help
```

## Try Without Installing

```bash
uvx oh-my-field --help
```

## Development Install

```bash
git clone https://github.com/Baekpica/oh-my-field.git
cd oh-my-field
uv sync --all-extras --dev
uv run omf --help
```

## Verify The Install

```bash
omf --help
omf import-run --help
omf capability export --help
```

From a source checkout, use `uv run omf ...`.
