#!/usr/bin/env bash
#
# 10-minute happy path: prove that a task a *bare* Haiku gets wrong becomes
# reproducible once Haiku is handed the OMF capability distilled from an Opus run.
#
# What it does:
#   [1/3] Rebuild the capability from the recorded Opus run (import-run -> promote)
#         into a scratch field, show `health`, then overlay the curated
#         manifest and instruction surface -- this is the OMF pipeline + curation.
#   [2/3] Ask Haiku to do the task from the BARE goal             -> expect FAIL.
#   [3/3] Ask Haiku to do the task WITH the promoted capability   -> expect PASS.
#
# Requirements: bash, python3, uv (for `omf`), and the `claude` CLI (logged in).
# Override the model with HAIKU_MODEL=... if needed.
set -euo pipefail

cd "$(dirname "$0")"
HERE="$(pwd)"
HAIKU_MODEL="${HAIKU_MODEL:-claude-haiku-4-5}"
OUT="$HERE/.omf-demo-out"
FIELD="$OUT/field"
rm -rf "$OUT"
mkdir -p "$OUT" "$FIELD/evidence" "$FIELD/capabilities" "$FIELD/evals"

OUTPUT_DIRECTIVE="Read input.csv and write the normalized result to output/normalized.json. Write only the JSON file; do not print the JSON to the chat."

hr() { printf '%s\n' "------------------------------------------------------------"; }

# Run Haiku as a real agent in an isolated scratch dir: it reads input.csv and
# writes output/normalized.json. acceptEdits lets it create files without
# prompting. $1 = run dir, $2 = prompt. Output path: <run dir>/output/normalized.json
run_haiku() {
  local run_dir="$1" prompt="$2"
  rm -rf "$run_dir"
  mkdir -p "$run_dir"
  cp task/messy_orders.csv "$run_dir/input.csv"
  ( cd "$run_dir" && claude -p --model "$HAIKU_MODEL" --permission-mode acceptEdits "$prompt" >agent.stdout 2>agent.stderr ) || true
}

# ---------------------------------------------------------------------------
hr; echo "[1/3] OMF pipeline: import the recorded Opus run, then promote it"; hr
# import-run resolves artifact paths relative to the log's directory, so we run
# it from seed/ (uv still finds the project from any subdir).
# --model records the source (Opus) model so the capability's runtime.model is
# set and the portability path scores this as an Opus -> Haiku downgrade.
EVIDENCE_JSON="$(cd seed && uv run omf import-run claude_code \
  --log opus_run.log \
  --goal "normalize a messy orders CSV into strict JSON" \
  --model claude-opus-4-1 \
  --artifact output/normalized.json \
  --test-result validation.txt \
  --outcome success \
  --evidence-dir "$FIELD/evidence")"
EVIDENCE_ID="$(printf '%s' "$EVIDENCE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_id"])')"
echo "imported evidence: $EVIDENCE_ID"

uv run omf promote "$EVIDENCE_ID" \
  --name csv_normalize \
  --description "Normalize a messy orders CSV into strict, schema-checked JSON" \
  --evidence-dir "$FIELD/evidence" \
  --capabilities-dir "$FIELD/capabilities" \
  --eval-dir "$FIELD/evals" >/dev/null
echo "promoted capability: csv_normalize"
uv run omf health csv_normalize \
  --capabilities-dir "$FIELD/capabilities" \
  --eval-dir "$FIELD/evals" | python3 -m json.tool

# promote scaffolds a generic manifest, instruction surface, and existence-only
# contract validator; the real workflow is to then curate it (OMF treats
# capabilities/<name>/ as the reviewable source of truth). Overlay the committed
# curated manifest + harness + instructions + contracts + validators onto the
# freshly promoted package, then rebind the copied manifest to this run's
# evidence id. That keeps the [3/3] prompt, `omf capability validate`, and
# `omf capability export` on THIS curated package -- not the generic scaffold.
FIELD_CAP="$FIELD/capabilities/csv_normalize"
echo "curating the promoted package with the reviewed manifest + contract surface"
uv run python curate_package.py \
  --source capabilities/csv_normalize \
  --target "$FIELD_CAP" \
  --evidence "$FIELD/evidence/$EVIDENCE_ID.json"

# ---------------------------------------------------------------------------
hr; echo "[2/3] Haiku with the BARE goal (no capability)"; hr
BARE_PROMPT="Normalize the messy orders CSV into a clean JSON document.
$OUTPUT_DIRECTIVE"
run_haiku "$OUT/bare_run" "$BARE_PROMPT"
set +e
python3 check.py "$OUT/bare_run/output/normalized.json"
BARE_RC=$?
set -e

# ---------------------------------------------------------------------------
hr; echo "[3/3] Haiku WITH the OMF capability (the package promoted above)"; hr
CAP_PROMPT="$(cat "$FIELD_CAP/instructions.md")

---
$OUTPUT_DIRECTIVE"
run_haiku "$OUT/cap_run" "$CAP_PROMPT"
set +e
python3 check.py "$OUT/cap_run/output/normalized.json"
CAP_RC=$?
set -e

# ---------------------------------------------------------------------------
hr; echo "RESULT (model: $HAIKU_MODEL)"; hr
bare_label=$([ $BARE_RC -eq 0 ] && echo "PASS" || echo "FAIL")
cap_label=$([ $CAP_RC -eq 0 ] && echo "PASS" || echo "FAIL")
echo "  bare goal           -> $bare_label   (output: $OUT/bare_run/output/normalized.json)"
echo "  with OMF capability -> $cap_label   (output: $OUT/cap_run/output/normalized.json)"
echo

# The capability run is the contract: it must PASS. Anything else (a real
# regression, a missing/unauthenticated `claude`, a bad model name -> no output
# file) is a failure the caller must be able to detect.
if [ $CAP_RC -ne 0 ]; then
  echo "FAILURE: the capability run did not produce the expected output."
  if [ ! -s "$OUT/cap_run/output/normalized.json" ]; then
    echo "No output file was written. Check that \`claude\` is installed and"
    echo "logged in, and that HAIKU_MODEL ('$HAIKU_MODEL') is a valid model."
    echo "Agent stderr: $OUT/cap_run/agent.stderr"
  fi
  exit 1
fi

if [ $BARE_RC -eq 0 ]; then
  echo "Heads up: the bare run also passed this time (model outputs vary)."
  echo "Re-run to see the typical FAIL -> PASS contrast."
  exit 0
fi

echo "Same model, same input. The only difference is the capability OMF carried"
echo "over from the Opus run -- and that is what made Haiku succeed."
exit 0
