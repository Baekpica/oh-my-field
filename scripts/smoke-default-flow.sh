#!/usr/bin/env bash
set -euo pipefail

input_package="${1:?usage: smoke-default-flow.sh <wheel-or-sdist-path>}"
package_dir="$(cd "$(dirname "$input_package")" && pwd)"
package_path="${package_dir}/$(basename "$input_package")"

if [[ ! -f "$package_path" ]]; then
  echo "package not found: $package_path" >&2
  exit 2
fi

: "${UV_CACHE_DIR:=${RUNNER_TEMP:-/tmp}/uv-cache}"
export UV_CACHE_DIR
mkdir -p "$UV_CACHE_DIR"

smoke_root="$(mktemp -d)"
cd "$smoke_root"

omf=(uv run --isolated --no-project --with "$package_path" omf)

"${omf[@]}" init

printf "agent run log\n" > codex.log
printf "pytest passed\n" > pytest.txt

evidence_json="$(
  "${omf[@]}" import-run codex \
    --log codex.log \
    --goal "triage repo issue" \
    --test-result pytest.txt \
    --outcome success
)"
evidence_id="$(
  python3 -c 'import json, sys; print(json.load(sys.stdin)["evidence_id"])' \
    <<<"$evidence_json"
)"

"${omf[@]}" promote "$evidence_id" \
  --name repo_issue_triage \
  --description "Repository issue triage capability"

"${omf[@]}" health repo_issue_triage

export_json="$("${omf[@]}" export repo_issue_triage --approve-export)"
export_path="$(
  python3 -c 'import json, sys; print(json.load(sys.stdin)["export_path"])' \
    <<<"$export_json"
)"

test -f capabilities/repo_issue_triage/capability.yaml
test -f "$export_path"
test ! -e .omf/capabilities/repo_issue_triage
