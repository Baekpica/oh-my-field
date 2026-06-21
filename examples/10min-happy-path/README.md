# 10-Minute Happy Path: Opus → Haiku

The fastest way to feel what OMF is for. In one sitting you watch a task that a
**bare Haiku gets wrong** become reproducible the moment Haiku is handed the OMF
capability that was **distilled from an Opus run**.

> Same model. Same input. The only thing that changes is the capability OMF
> carried over — and that is what makes the cheaper model succeed.

## The task

Turn a deliberately messy orders CSV ([`task/messy_orders.csv`](task/messy_orders.csv))
into one strict JSON document — exact key set, ISO dates, numeric amounts,
boolean flags, blank rows dropped, duplicates removed, sorted by `order_id`.
Easy to *almost* get right, which is exactly why a bare prompt fails the contract.

## Run it

```bash
# from the repo root; requires uv, python3, and the `claude` CLI (logged in)
bash examples/10min-happy-path/run.sh
```

You will see three steps:

1. **OMF pipeline** — `omf import-run` the recorded Opus run, then `omf promote`
   it into a capability, then `omf health`.
2. **Bare Haiku** — runs as an agent (reads `input.csv`, writes
   `output/normalized.json`) given only the goal → **FAIL** (top-level array,
   wrong keys, kept rows that should be dropped…).
3. **Haiku + OMF capability** — same agent setup, but handed the distilled
   `instructions.md` → **PASS**.

```
  bare goal           -> FAIL   (output: .omf-demo-out/bare_run/output/normalized.json)
  with OMF capability -> PASS   (output: .omf-demo-out/cap_run/output/normalized.json)
```

The verdict is objective: [`check.py`](check.py) does a *semantic* deep-equal of
the produced JSON against the committed golden
[`expected/normalized.json`](expected/normalized.json) (values must match;
whitespace / key order / `2000` vs `2000.0` do not).

> Verified during authoring against `claude-haiku-4-5`: the bare goal fails every
> run, and the capability passes reliably (4/4 on the final check after the drop
> rules were hardened). Outputs vary run-to-run; re-run to see the typical
> FAIL → PASS.

## What's in here

| Path | Role |
|------|------|
| `task/messy_orders.csv` | the messy input a user "has" |
| `seed/` | the recorded Opus run fed to `import-run` (`opus_run.log`, `output/normalized.json`, `validation.txt`, `spec.md`) |
| `capabilities/csv_normalize/` | the promoted + curated capability package (the reviewable source of truth) |
| `expected/normalized.json` | the golden output |
| `check.py` | the objective pass/fail |
| `run.sh` | the one-command demo |

## Do it yourself (the CLI behind the script)

```bash
# Use one shared field directory so import and promote agree on where evidence
# lives (import-run defaults --evidence-dir to .omf/evidence under its cwd).
FIELD="$(pwd)/.omf-quickstart"

# 1. Import the recorded Opus run as evidence (run from seed/ so artifact
#    paths resolve relative to the log's directory).
( cd examples/10min-happy-path/seed && uv run omf import-run claude_code \
  --log opus_run.log \
  --goal "normalize a messy orders CSV into strict JSON" \
  --artifact output/normalized.json \
  --test-result validation.txt \
  --outcome success \
  --evidence-dir "$FIELD/evidence" )

# 2. Promote the evidence into a capability (copy the evidence_id from step 1).
uv run omf promote <evidence_id> \
  --name csv_normalize \
  --description "Normalize a messy orders CSV into strict, schema-checked JSON" \
  --evidence-dir "$FIELD/evidence" \
  --capabilities-dir "$FIELD/capabilities"

# 3. See its health / portability status.
uv run omf health csv_normalize --capabilities-dir "$FIELD/capabilities"

# 4. Curate the promoted scaffold. `promote` renders a generic instruction
#    surface and an existence-only contract validator, so overlay the reviewed
#    instructions + contracts + validators (capabilities/<name>/ is the
#    human-reviewable source of truth). This is the same curation run.sh performs
#    before the Haiku run -- without it, export/validate below carries the
#    generic scaffold instead of the rules that make the PASS reproducible.
DIY_CAP="$FIELD/capabilities/csv_normalize"
cp examples/10min-happy-path/capabilities/csv_normalize/instructions.md "$DIY_CAP/instructions.md"
cp -r examples/10min-happy-path/capabilities/csv_normalize/contracts \
      examples/10min-happy-path/capabilities/csv_normalize/validators "$DIY_CAP/"

# 5. (Portability) export the curated capability for another runtime.
uv run omf capability export csv_normalize \
  --target claude_code --target-model claude-haiku-4-5 \
  --capabilities-dir "$FIELD/capabilities" \
  --out "$FIELD/exports/csv_normalize-haiku"
```

The committed `capabilities/csv_normalize/` (instructions + contracts + validators)
was curated from the promoted scaffold — `capabilities/<name>/` is the
human-reviewable source of truth, so refining it after `promote` (step 4 above) is
the intended flow, and exporting/validating only makes sense once it is applied.
