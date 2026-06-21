#!/usr/bin/env bash
#
# 10-minute Codex happy path: prove that a portfolio backtest a bare smaller
# Codex model can get wrong becomes reproducible once it is handed the OMF
# capability distilled from a stronger Codex run.
#
# What it does:
#   [1/3] Rebuild the capability from the recorded gpt-5.5 run
#         (import-run -> promote), show health, then overlay the reviewed
#         manifest/instructions/contracts/validator.
#   [2/3] Ask gpt-5.4-mini to do the task from the BARE goal -> expect FAIL.
#   [3/3] Ask gpt-5.4-mini to do the task WITH the capability -> expect PASS.
#
# Requirements: bash, python3, uv, and the `codex` CLI (logged in).
# Override with SOURCE_MODEL=..., TARGET_MODEL=..., or TARGET_REASONING=...
# if needed.
set -euo pipefail

cd "$(dirname "$0")"
HERE="$(pwd)"
SOURCE_MODEL="${SOURCE_MODEL:-gpt-5.5}"
TARGET_MODEL="${TARGET_MODEL:-gpt-5.4-mini}"
TARGET_REASONING="${TARGET_REASONING:-medium}"
OUT="$HERE/.omf-demo-out"
FIELD="$OUT/field"
rm -rf "$OUT"
mkdir -p "$OUT" "$FIELD/evidence" "$FIELD/capabilities" "$FIELD/evals"

OUTPUT_DIRECTIVE="Read input.md and write the completed Markdown report to output/backtest_report.md. Do not stop until the file exists."

hr() { printf '%s\n' "------------------------------------------------------------"; }

run_codex() {
  local run_dir="$1" prompt="$2"
  rm -rf "$run_dir"
  mkdir -p "$run_dir"
  cp task/backtest_case.md "$run_dir/input.md"
  (
    cd "$run_dir"
    codex exec \
      --skip-git-repo-check \
      --ephemeral \
      --sandbox workspace-write \
      -c 'approval_policy="never"' \
      -c "model_reasoning_effort=\"$TARGET_REASONING\"" \
      --model "$TARGET_MODEL" \
      "$prompt" >agent.stdout 2>agent.stderr
  ) || true
}

hr; echo "[1/3] OMF pipeline: import the recorded Codex gpt-5.5 run, then promote it"; hr
EVIDENCE_JSON="$(cd seed && uv run omf import-run codex \
  --log gpt55_run.txt \
  --goal "produce a portfolio backtest report for the six-month model portfolio case" \
  --model "$SOURCE_MODEL" \
  --artifact output/backtest_report.md \
  --test-result validation.txt \
  --outcome success \
  --evidence-dir "$FIELD/evidence")"
EVIDENCE_ID="$(printf '%s' "$EVIDENCE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_id"])')"
echo "imported evidence: $EVIDENCE_ID"

uv run omf promote "$EVIDENCE_ID" \
  --name portfolio_backtest \
  --description "Produce a deterministic portfolio backtest report with rebalance costs and risk metrics" \
  --evidence-dir "$FIELD/evidence" \
  --capabilities-dir "$FIELD/capabilities" \
  --eval-dir "$FIELD/evals" >/dev/null
echo "promoted capability: portfolio_backtest"
uv run omf health portfolio_backtest \
  --capabilities-dir "$FIELD/capabilities" \
  --eval-dir "$FIELD/evals" | python3 -m json.tool

FIELD_CAP="$FIELD/capabilities/portfolio_backtest"
echo "curating the promoted package with the reviewed manifest + contract surface"
uv run python curate_package.py \
  --source capabilities/portfolio_backtest \
  --target "$FIELD_CAP" \
  --evidence "$FIELD/evidence/$EVIDENCE_ID.json"

hr; echo "[2/3] Codex $TARGET_MODEL with the BARE goal (no capability)"; hr
BARE_PROMPT="Produce the requested portfolio backtest report.
$OUTPUT_DIRECTIVE"
run_codex "$OUT/bare_run" "$BARE_PROMPT"
set +e
python3 check.py "$OUT/bare_run/output/backtest_report.md"
BARE_RC=$?
set -e

hr; echo "[3/3] Codex $TARGET_MODEL WITH the OMF capability"; hr
CAP_PROMPT="$(cat "$FIELD_CAP/instructions.md")

---
$OUTPUT_DIRECTIVE"
run_codex "$OUT/cap_run" "$CAP_PROMPT"
set +e
python3 check.py "$OUT/cap_run/output/backtest_report.md"
CAP_RC=$?
set -e

hr; echo "RESULT (source: $SOURCE_MODEL, target: $TARGET_MODEL, reasoning: $TARGET_REASONING)"; hr
bare_label=$([ $BARE_RC -eq 0 ] && echo "PASS" || echo "FAIL")
cap_label=$([ $CAP_RC -eq 0 ] && echo "PASS" || echo "FAIL")
echo "  bare goal           -> $bare_label   (output: $OUT/bare_run/output/backtest_report.md)"
echo "  with OMF capability -> $cap_label   (output: $OUT/cap_run/output/backtest_report.md)"
echo

if [ $CAP_RC -ne 0 ]; then
  echo "FAILURE: the capability run did not produce the expected report."
  if [ ! -s "$OUT/cap_run/output/backtest_report.md" ]; then
    echo "No report was written. Check that \`codex\` is installed and logged in,"
    echo "and that TARGET_MODEL ('$TARGET_MODEL') is a valid model."
    echo "Agent stderr: $OUT/cap_run/agent.stderr"
  fi
  exit 1
fi

if [ $BARE_RC -eq 0 ]; then
  echo "Heads up: the bare run also passed this time (model outputs vary)."
  echo "Re-run to see the typical FAIL -> PASS contrast."
  exit 0
fi

echo "Same target model, same input. The only difference is the OMF capability"
echo "carried over from the stronger Codex run."
exit 0
