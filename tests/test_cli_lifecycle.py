from __future__ import annotations

import json
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]


def test_console_script_exposes_implemented_commands() -> None:
    omf_executable = shutil.which("omf")
    assert omf_executable is not None
    result = subprocess.run(
        [omf_executable, "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    for command in (
        "capture",
        "promote",
        "replay",
        "eval",
        "learn",
        "list",
        "inspect",
        "regress",
        "review",
        "search",
    ):
        assert command in result.stdout


def run_omf(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "omf.cli", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    git_executable = shutil.which("git")
    assert git_executable is not None
    return subprocess.run(
        [git_executable, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def parse_json(stdout: str) -> dict[str, object]:
    loaded = cast("object", json.loads(stdout))
    assert isinstance(loaded, dict)
    return cast("dict[str, object]", loaded)


def get_str(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    assert isinstance(value, str)
    return value


def get_int(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    assert isinstance(value, int)
    return value


def get_float(payload: dict[str, object], key: str) -> float:
    value = payload[key]
    assert isinstance(value, float)
    return value


def get_list(payload: dict[str, object], key: str) -> list[object]:
    value = payload[key]
    assert isinstance(value, list)
    return cast("list[object]", value)


def get_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def write_script(path: Path, artifact_name: str, content: str) -> None:
    _ = path.write_text(
        "\n".join(
            (
                "from pathlib import Path",
                f"Path({artifact_name!r}).write_text({content!r}, encoding='utf-8')",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def write_check_script(path: Path, artifact_name: str, expected_content: str) -> None:
    _ = path.write_text(
        "\n".join(
            (
                "from pathlib import Path",
                f"actual = Path({artifact_name!r}).read_text(encoding='utf-8')",
                f"raise SystemExit(0 if actual == {expected_content!r} else 2)",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rewrite_json_field(path: Path, key: str, value: object) -> None:
    loaded = cast("object", json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(loaded, dict)
    payload = cast("dict[str, object]", loaded)
    payload[key] = value
    _ = path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_capture_runs_real_shell_command_syntax(tmp_path: Path) -> None:
    store_dir = tmp_path / ".omf"

    capture = run_omf(
        "capture",
        "--goal",
        "prove shell command execution",
        "--command",
        "printf '%s' 'shell verified' > artifact.txt",
        "--artifact",
        "artifact.txt",
        "--check",
        '[ "$(cat artifact.txt)" = "shell verified" ]',
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )

    assert capture.returncode == 0, capture.stderr
    capture_payload = parse_json(capture.stdout)
    command_result = get_dict(capture_payload["command_result"])
    artifact_payload = get_dict(get_list(capture_payload, "artifacts")[0])
    harness_results = [
        get_dict(result) for result in get_list(capture_payload, "harness_results")
    ]
    recorded_args = get_list(command_result, "args")
    assert get_str(capture_payload, "status") == "pass"
    assert recorded_args[-2:] == ["-c", "printf '%s' 'shell verified' > artifact.txt"]
    assert artifact_payload["exists"] is True
    assert (tmp_path / "artifact.txt").read_text(encoding="utf-8") == "shell verified"
    assert get_str(harness_results[0], "status") == "pass"


def test_capture_promote_replay_eval_lifecycle_uses_real_artifacts(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    check_path = tmp_path / "check_artifact.py"
    write_script(script_path, "artifact.txt", "verified artifact")
    write_check_script(check_path, "artifact.txt", "verified artifact")
    store_dir = tmp_path / ".omf"

    capture = run_omf(
        "capture",
        "--goal",
        "prove artifact generation",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--check",
        f"{sys.executable} {check_path}",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )

    assert capture.returncode == 0, capture.stderr
    capture_payload = parse_json(capture.stdout)
    evidence_path = Path(get_str(capture_payload, "evidence_path"))
    artifacts = get_list(capture_payload, "artifacts")
    artifact_payload = get_dict(artifacts[0])
    assert get_str(capture_payload, "status") == "pass"
    assert artifact_payload["exists"] is True
    assert artifact_payload["sha256"]
    harness_results = [get_dict(result) for result in get_list(capture_payload, "harness_results")]
    assert get_str(harness_results[0], "status") == "pass"
    assert evidence_path.exists()

    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "artifact lifecycle",
        "--store-dir",
        str(store_dir),
    )

    assert promote.returncode == 0, promote.stderr
    promote_payload = parse_json(promote.stdout)
    manifest_path = Path(get_str(promote_payload, "manifest_path"))
    assert get_str(promote_payload, "name") == "artifact-lifecycle"
    assert get_str(promote_payload, "source_evidence_sha256") == sha256_file(evidence_path)
    assert len(get_list(promote_payload, "required_checks")) == 1
    assert manifest_path.exists()

    replay = run_omf("replay", str(manifest_path), "--store-dir", str(store_dir))

    assert replay.returncode == 0, replay.stderr
    replay_payload = parse_json(replay.stdout)
    replay_checks = [get_dict(check) for check in get_list(replay_payload, "checks")]
    replay_timing = get_dict(replay_payload["timing"])
    assert get_str(replay_payload, "status") == "pass"
    assert all(check["status"] == "pass" for check in replay_checks)
    assert any(str(check["name"]).startswith("harness:") for check in replay_checks)
    assert get_int(replay_timing, "command_duration_ms") >= 0
    assert get_int(replay_timing, "harness_duration_ms") >= 0
    assert get_int(replay_timing, "total_command_and_harness_duration_ms") == (
        get_int(replay_timing, "command_duration_ms")
        + get_int(replay_timing, "harness_duration_ms")
    )

    eval_result = run_omf(
        "eval",
        str(manifest_path),
        "--runs",
        "2",
        "--store-dir",
        str(store_dir),
    )

    assert eval_result.returncode == 0, eval_result.stderr
    eval_payload = parse_json(eval_result.stdout)
    assert get_str(eval_payload, "status") == "pass"
    assert get_int(eval_payload, "runs") == 2
    assert get_int(eval_payload, "pass_count") == 2
    assert get_float(eval_payload, "pass_rate") == 1.0
    eval_timing = get_dict(eval_payload["timing"])
    assert get_int(eval_timing, "command_duration_ms_min") >= 0
    assert get_int(eval_timing, "command_duration_ms_max") >= get_int(
        eval_timing, "command_duration_ms_min"
    )
    assert get_float(eval_timing, "command_duration_ms_mean") >= 0
    assert get_int(eval_timing, "harness_duration_ms_total") >= 0
    assert get_int(eval_timing, "total_command_and_harness_duration_ms") >= 0
    eval_path = Path(get_str(eval_payload, "eval_path"))

    review = run_omf(
        "review",
        str(eval_path),
        "--reviewer",
        "qa-reviewer",
        "--decision",
        "approve",
        "--note",
        "approved after real replay and eval artifacts passed",
        "--store-dir",
        str(store_dir),
    )

    assert review.returncode == 0, review.stderr
    review_payload = parse_json(review.stdout)
    review_path = Path(get_str(review_payload, "review_path"))
    assert get_str(review_payload, "decision") == "approve"
    assert get_str(review_payload, "reviewer") == "qa-reviewer"
    assert get_str(review_payload, "reviewed_artifact_type") == "eval"
    assert get_str(review_payload, "reviewed_artifact_status") == "pass"
    assert get_str(review_payload, "reviewed_artifact_sha256")
    assert review_path.exists()

    regression = run_omf(
        "regress",
        str(manifest_path),
        "--source-artifact",
        str(review_path),
        "--name",
        "artifact lifecycle regression",
        "--reason",
        "review requested a regression case from a verified eval artifact",
        "--store-dir",
        str(store_dir),
    )

    assert regression.returncode == 0, regression.stderr
    regression_payload = parse_json(regression.stdout)
    regression_path = Path(get_str(regression_payload, "regression_path"))
    assert get_str(regression_payload, "name") == "artifact-lifecycle-regression"
    assert get_str(regression_payload, "status") == "pass"
    assert get_str(regression_payload, "source_artifact_type") == "review"
    assert get_str(regression_payload, "source_artifact_status") == "approve"
    regression_replay = get_dict(regression_payload["replay_result"])
    assert get_str(regression_replay, "status") == "pass"
    assert regression_path.exists()

    learning = run_omf(
        "learn",
        "--source-artifact",
        str(eval_path),
        "--source-artifact",
        str(review_path),
        "--source-artifact",
        str(regression_path),
        "--name",
        "artifact lifecycle learning",
        "--purpose",
        "prompt_improvement",
        "--note",
        "exported from verified lifecycle artifacts",
        "--store-dir",
        str(store_dir),
    )

    assert learning.returncode == 0, learning.stderr
    learning_payload = parse_json(learning.stdout)
    learning_path = Path(get_str(learning_payload, "manifest_path"))
    learning_jsonl_path = Path(get_str(learning_payload, "output_jsonl_path"))
    learning_items = [get_dict(item) for item in get_list(learning_payload, "items")]
    assert get_str(learning_payload, "name") == "artifact-lifecycle-learning"
    assert get_str(learning_payload, "purpose") == "prompt_improvement"
    assert get_int(learning_payload, "item_count") == 3
    assert len(learning_items) == 3
    assert learning_path.exists()
    assert learning_jsonl_path.exists()
    assert get_str(learning_payload, "output_jsonl_sha256") == sha256_file(
        learning_jsonl_path
    )
    assert {get_str(item, "source_artifact_type") for item in learning_items} == {
        "eval",
        "review",
        "regression",
    }

    list_result = run_omf("list", "--store-dir", str(store_dir))

    assert list_result.returncode == 0, list_result.stderr
    list_payload = parse_json(list_result.stdout)
    entries = [get_dict(entry) for entry in get_list(list_payload, "entries")]
    entry_kinds = {get_str(entry, "kind") for entry in entries}
    assert {
        "evidence",
        "capability",
        "replay",
        "eval",
        "review",
        "regression",
        "learning",
    }.issubset(entry_kinds)
    assert all(entry["validated"] is True for entry in entries)
    entries_by_kind = {get_str(entry, "kind"): entry for entry in entries}
    assert get_str(entries_by_kind["capability"], "status") == "ready"
    assert get_str(entries_by_kind["review"], "status") == "approve"
    assert get_str(entries_by_kind["regression"], "status") == "pass"
    assert get_str(entries_by_kind["learning"], "status") == "prompt_improvement"

    replay_path = Path(get_str(replay_payload, "replay_path"))
    for path, artifact_type in (
        (evidence_path, "evidence"),
        (manifest_path, "capability"),
        (replay_path, "replay"),
        (eval_path, "eval"),
        (review_path, "review"),
        (regression_path, "regression"),
        (learning_path, "learning"),
    ):
        inspect_result = run_omf("inspect", str(path))
        assert inspect_result.returncode == 0, inspect_result.stderr
        inspect_payload = parse_json(inspect_result.stdout)
        assert get_str(inspect_payload, "artifact_type") == artifact_type
        inspect_summary = get_dict(inspect_payload["summary"])
        assert inspect_summary
        if artifact_type in {"replay", "eval"}:
            assert get_int(inspect_summary, "total_command_and_harness_duration_ms") >= 0
        if artifact_type == "replay":
            assert inspect_summary["manifest_verified"] is True
            assert inspect_summary["evidence_verified"] is True
            assert get_str(inspect_summary, "manifest_sha256") == sha256_file(
                manifest_path
            )
            assert get_str(inspect_summary, "evidence_sha256") == sha256_file(
                Path(get_str(replay_payload, "evidence_path"))
            )
        if artifact_type == "eval":
            assert inspect_summary["replay_results_verified"] is True
        if artifact_type == "capability":
            assert inspect_summary["source_evidence_verified"] is True
            assert get_str(inspect_summary, "source_evidence_sha256") == sha256_file(
                evidence_path
            )
        if artifact_type == "review":
            assert get_str(inspect_summary, "decision") == "approve"
            assert inspect_summary["reviewed_artifact_verified"] is True
            assert get_str(inspect_summary, "reviewed_artifact_sha256") == sha256_file(
                eval_path
            )
        if artifact_type == "regression":
            assert get_str(inspect_summary, "replay_status") == "pass"
            assert inspect_summary["source_artifact_verified"] is True
            assert inspect_summary["manifest_verified"] is True
            assert get_str(inspect_summary, "source_artifact_sha256") == sha256_file(
                review_path
            )
            assert get_str(inspect_summary, "manifest_sha256") == sha256_file(
                manifest_path
            )
        if artifact_type == "learning":
            assert get_int(inspect_summary, "item_count") == 3
            assert inspect_summary["output_jsonl_verified"] is True
            assert inspect_summary["source_artifacts_verified"] is True
            assert get_int(inspect_summary, "source_artifact_count") == 3
            assert get_str(inspect_summary, "output_jsonl_sha256") == sha256_file(
                learning_jsonl_path
            )

    search_result = run_omf(
        "search",
        "prove artifact generation",
        "--store-dir",
        str(store_dir),
    )

    assert search_result.returncode == 0, search_result.stderr
    search_payload = parse_json(search_result.stdout)
    matches = [get_dict(match) for match in get_list(search_payload, "matches")]
    assert matches
    assert any(get_str(match, "kind") == "capability" for match in matches)
    assert all(get_int(match, "score") > 0 for match in matches)
    assert all(match["validated"] is True for match in matches)

    filtered_search = run_omf(
        "search",
        "artifact-lifecycle",
        "--kind",
        "capability",
        "--store-dir",
        str(store_dir),
    )

    assert filtered_search.returncode == 0, filtered_search.stderr
    filtered_payload = parse_json(filtered_search.stdout)
    filtered_matches = [
        get_dict(match) for match in get_list(filtered_payload, "matches")
    ]
    assert filtered_matches
    assert all(get_str(match, "kind") == "capability" for match in filtered_matches)
    assert all(get_str(match, "status") == "ready" for match in filtered_matches)
    assert all(match["validated"] is True for match in filtered_matches)

    review_search = run_omf(
        "search",
        "approved after real replay",
        "--kind",
        "review",
        "--store-dir",
        str(store_dir),
    )

    assert review_search.returncode == 0, review_search.stderr
    review_search_payload = parse_json(review_search.stdout)
    review_matches = [get_dict(match) for match in get_list(review_search_payload, "matches")]
    assert review_matches
    assert all(get_str(match, "kind") == "review" for match in review_matches)
    assert all(get_str(match, "status") == "approve" for match in review_matches)
    assert all(match["validated"] is True for match in review_matches)

    regression_search = run_omf(
        "search",
        "review requested a regression case",
        "--kind",
        "regression",
        "--store-dir",
        str(store_dir),
    )

    assert regression_search.returncode == 0, regression_search.stderr
    regression_search_payload = parse_json(regression_search.stdout)
    regression_matches = [
        get_dict(match) for match in get_list(regression_search_payload, "matches")
    ]
    assert regression_matches
    assert all(get_str(match, "kind") == "regression" for match in regression_matches)
    assert all(get_str(match, "status") == "pass" for match in regression_matches)
    assert all(match["validated"] is True for match in regression_matches)

    learning_search = run_omf(
        "search",
        "exported from verified lifecycle artifacts",
        "--kind",
        "learning",
        "--store-dir",
        str(store_dir),
    )

    assert learning_search.returncode == 0, learning_search.stderr
    learning_search_payload = parse_json(learning_search.stdout)
    learning_matches = [get_dict(match) for match in get_list(learning_search_payload, "matches")]
    assert learning_matches
    assert all(get_str(match, "kind") == "learning" for match in learning_matches)
    assert all(get_str(match, "status") == "prompt_improvement" for match in learning_matches)
    assert all(match["validated"] is True for match in learning_matches)


def test_search_rejects_unknown_artifact_kind(tmp_path: Path) -> None:
    store_dir = tmp_path / ".omf"
    search_result = run_omf(
        "search",
        "anything",
        "--kind",
        "unknown",
        "--store-dir",
        str(store_dir),
    )

    assert search_result.returncode != 0
    assert "Unsupported artifact kind" in search_result.stderr


def test_list_rejects_invalid_artifact(tmp_path: Path) -> None:
    store_dir = tmp_path / ".omf"
    evidence_dir = store_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    _ = (evidence_dir / "bad.json").write_text(
        json.dumps(
            {
                "schema_version": "omf.evidence.v1",
                "goal": "invalid list artifact",
            }
        ),
        encoding="utf-8",
    )

    list_result = run_omf("list", "--store-dir", str(store_dir))

    assert list_result.returncode != 0
    assert "Invalid evidence record" in list_result.stderr
    assert "Traceback" not in list_result.stderr


def test_list_rejects_artifact_in_wrong_store_bucket(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "wrong list bucket")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "wrong list bucket artifact",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    reviews_dir = store_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    misplaced_path = reviews_dir / "misplaced.json"
    _ = misplaced_path.write_text(evidence_path.read_text(encoding="utf-8"), encoding="utf-8")

    list_result = run_omf("list", "--store-dir", str(store_dir))

    assert list_result.returncode != 0
    assert "List artifact kind does not match store location" in list_result.stderr
    assert "Traceback" not in list_result.stderr


def test_inspect_rejects_evidence_with_tampered_artifact(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "evidence artifact")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture tamperable evidence artifact",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    _ = (tmp_path / "artifact.txt").write_text("tampered artifact\n", encoding="utf-8")

    inspect_result = run_omf("inspect", str(evidence_path))

    assert inspect_result.returncode != 0
    assert "Evidence artifact hash does not match evidence record" in inspect_result.stderr

    list_result = run_omf("list", "--store-dir", str(store_dir))

    assert list_result.returncode != 0
    assert "Evidence artifact hash does not match evidence record" in list_result.stderr
    assert "Traceback" not in list_result.stderr


def test_promote_rejects_evidence_with_tampered_status(tmp_path: Path) -> None:
    script_path = tmp_path / "fail.py"
    _ = script_path.write_text("raise SystemExit(7)\n", encoding="utf-8")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture status tamper target",
        "--command",
        f"{sys.executable} {script_path}",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    _ = evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace(
            '"status": "fail"',
            '"status": "pass"',
            1,
        ),
        encoding="utf-8",
    )

    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "fake passing evidence",
        "--store-dir",
        str(store_dir),
    )

    assert promote.returncode != 0
    assert "Evidence record does not match command, harness, or artifact results" in promote.stderr


def test_search_rejects_matching_invalid_artifact(tmp_path: Path) -> None:
    store_dir = tmp_path / ".omf"
    evidence_dir = store_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    _ = (evidence_dir / "bad.json").write_text(
        json.dumps(
            {
                "schema_version": "omf.evidence.v1",
                "goal": "find invalid search artifact",
            }
        ),
        encoding="utf-8",
    )

    search_result = run_omf(
        "search",
        "find invalid search artifact",
        "--store-dir",
        str(store_dir),
    )

    assert search_result.returncode != 0
    assert "Invalid evidence record" in search_result.stderr


def test_search_rejects_artifact_in_wrong_store_bucket(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "wrong bucket")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "wrong bucket search artifact",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    reviews_dir = store_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    misplaced_path = reviews_dir / "misplaced.json"
    _ = misplaced_path.write_text(evidence_path.read_text(encoding="utf-8"), encoding="utf-8")

    search_result = run_omf(
        "search",
        "wrong bucket search artifact",
        "--kind",
        "review",
        "--store-dir",
        str(store_dir),
    )

    assert search_result.returncode != 0
    assert "List artifact kind does not match store location" in search_result.stderr


def test_inspect_rejects_learning_export_with_tampered_jsonl(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "learning source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture learning source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))

    learning = run_omf(
        "learn",
        "--source-artifact",
        str(evidence_path),
        "--name",
        "tamper detection",
        "--purpose",
        "eval_set",
        "--note",
        "exported from real evidence",
        "--store-dir",
        str(store_dir),
    )
    assert learning.returncode == 0, learning.stderr
    learning_payload = parse_json(learning.stdout)
    learning_path = Path(get_str(learning_payload, "manifest_path"))
    learning_jsonl_path = Path(get_str(learning_payload, "output_jsonl_path"))
    _ = learning_jsonl_path.write_text(
        learning_jsonl_path.read_text(encoding="utf-8").replace(
            "exported from real evidence",
            "tampered after export",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(learning_path))

    assert inspect_result.returncode != 0
    assert "Learning export JSONL hash does not match manifest" in inspect_result.stderr


def test_inspect_rejects_learning_export_with_tampered_source_artifact(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "learning source artifact")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture learning source artifact",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))

    learning = run_omf(
        "learn",
        "--source-artifact",
        str(evidence_path),
        "--name",
        "source tamper detection",
        "--purpose",
        "eval_set",
        "--note",
        "exported from verified source artifact",
        "--store-dir",
        str(store_dir),
    )
    assert learning.returncode == 0, learning.stderr
    learning_path = Path(get_str(parse_json(learning.stdout), "manifest_path"))
    _ = evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace(
            "capture learning source artifact",
            "tampered learning source artifact",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(learning_path))

    assert inspect_result.returncode != 0
    assert "Learning source artifact hash does not match manifest" in inspect_result.stderr


def test_inspect_rejects_learning_export_with_missing_source_artifact(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "missing learning source artifact")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture missing learning source artifact",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))

    learning = run_omf(
        "learn",
        "--source-artifact",
        str(evidence_path),
        "--name",
        "missing source detection",
        "--purpose",
        "eval_set",
        "--note",
        "exported from source artifact that must still exist",
        "--store-dir",
        str(store_dir),
    )
    assert learning.returncode == 0, learning.stderr
    learning_path = Path(get_str(parse_json(learning.stdout), "manifest_path"))
    evidence_path.unlink()

    inspect_result = run_omf("inspect", str(learning_path))

    assert inspect_result.returncode != 0
    assert "Learning source artifact does not exist" in inspect_result.stderr


def test_inspect_rejects_capability_with_tampered_source_evidence(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "capability source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture capability source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "tamper evidence",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    _ = evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace(
            "capture capability source",
            "tampered capability source",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(manifest_path))

    assert inspect_result.returncode != 0
    assert "Capability source evidence hash does not match manifest" in inspect_result.stderr


def test_replay_rejects_tampered_manifest_before_creating_replay(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "invalid replay manifest source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture invalid replay manifest source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "invalid replay manifest",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    rewrite_json_field(manifest_path, "source_evidence_sha256", "0" * 64)

    replay = run_omf("replay", str(manifest_path), "--store-dir", str(store_dir))

    assert replay.returncode != 0
    assert "Capability source evidence hash does not match manifest" in replay.stderr
    assert not list((store_dir / "replays").glob("*.json"))


def test_eval_rejects_tampered_manifest_before_creating_eval(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "invalid eval manifest source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture invalid eval manifest source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "invalid eval manifest",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    rewrite_json_field(manifest_path, "source_evidence_sha256", "0" * 64)

    eval_result = run_omf(
        "eval",
        str(manifest_path),
        "--runs",
        "1",
        "--store-dir",
        str(store_dir),
    )

    assert eval_result.returncode != 0
    assert "Capability source evidence hash does not match manifest" in eval_result.stderr
    assert not list((store_dir / "evals").glob("*.json"))
    assert not list((store_dir / "replays").glob("*.json"))


def test_regress_rejects_tampered_manifest_before_creating_case(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "invalid regression manifest source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture invalid regression manifest source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "invalid regression manifest",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    rewrite_json_field(manifest_path, "source_evidence_sha256", "0" * 64)

    regression = run_omf(
        "regress",
        str(manifest_path),
        "--source-artifact",
        str(evidence_path),
        "--name",
        "invalid regression manifest",
        "--reason",
        "should not create a case from an invalid manifest",
        "--store-dir",
        str(store_dir),
    )

    assert regression.returncode != 0
    assert "Capability source evidence hash does not match manifest" in regression.stderr
    assert not list((store_dir / "regressions").glob("*.json"))
    assert not list((store_dir / "replays").glob("*.json"))


def test_inspect_rejects_replay_with_tampered_evidence(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "replay source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture replay source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "replay tamper target",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    replay = run_omf("replay", str(manifest_path), "--store-dir", str(store_dir))
    assert replay.returncode == 0, replay.stderr
    replay_payload = parse_json(replay.stdout)
    replay_path = Path(get_str(replay_payload, "replay_path"))
    replay_evidence_path = Path(get_str(replay_payload, "evidence_path"))
    _ = replay_evidence_path.write_text(
        replay_evidence_path.read_text(encoding="utf-8").replace(
            "Replay capability replay-tamper-target",
            "tampered replay evidence",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(replay_path))

    assert inspect_result.returncode != 0
    assert "Replay evidence hash does not match replay record" in inspect_result.stderr


def test_inspect_rejects_eval_with_tampered_replay_evidence(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "eval source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture eval source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "eval tamper target",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    eval_result = run_omf(
        "eval",
        str(manifest_path),
        "--runs",
        "1",
        "--store-dir",
        str(store_dir),
    )
    assert eval_result.returncode == 0, eval_result.stderr
    eval_payload = parse_json(eval_result.stdout)
    eval_path = Path(get_str(eval_payload, "eval_path"))
    replay_results = [get_dict(item) for item in get_list(eval_payload, "replay_results")]
    replay_evidence_path = Path(get_str(replay_results[0], "evidence_path"))
    _ = replay_evidence_path.write_text(
        replay_evidence_path.read_text(encoding="utf-8").replace(
            "Replay capability eval-tamper-target",
            "tampered eval replay evidence",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(eval_path))

    assert inspect_result.returncode != 0
    assert "Replay evidence hash does not match replay record" in inspect_result.stderr


def test_inspect_rejects_review_with_tampered_reviewed_artifact(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "review source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture review source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    review = run_omf(
        "review",
        str(evidence_path),
        "--reviewer",
        "qa-reviewer",
        "--decision",
        "approve",
        "--note",
        "approved real evidence",
        "--store-dir",
        str(store_dir),
    )
    assert review.returncode == 0, review.stderr
    review_path = Path(get_str(parse_json(review.stdout), "review_path"))
    _ = evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace(
            "capture review source",
            "tampered review source",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(review_path))

    assert inspect_result.returncode != 0
    assert "Reviewed artifact hash does not match review record" in inspect_result.stderr


def test_inspect_rejects_regression_with_tampered_manifest(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "regression source")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture regression source",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "regression tamper target",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))
    regression = run_omf(
        "regress",
        str(manifest_path),
        "--source-artifact",
        str(evidence_path),
        "--name",
        "regression manifest tamper",
        "--reason",
        "created from verified evidence",
        "--store-dir",
        str(store_dir),
    )
    assert regression.returncode == 0, regression.stderr
    regression_path = Path(get_str(parse_json(regression.stdout), "regression_path"))
    _ = manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "regression-tamper-target",
            "tampered-regression-target",
        ),
        encoding="utf-8",
    )

    inspect_result = run_omf("inspect", str(regression_path))

    assert inspect_result.returncode != 0
    assert (
        "Regression capability manifest hash does not match case record"
        in inspect_result.stderr
    )


def test_review_rejects_unknown_decision(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "review target")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture review target",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))

    review = run_omf(
        "review",
        str(evidence_path),
        "--reviewer",
        "qa-reviewer",
        "--decision",
        "maybe",
        "--note",
        "invalid decision should fail",
        "--store-dir",
        str(store_dir),
    )

    assert review.returncode != 0
    assert "Unsupported review decision" in review.stderr


def test_regress_rejects_empty_reason(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    write_script(script_path, "artifact.txt", "regression target")
    store_dir = tmp_path / ".omf"
    capture = run_omf(
        "capture",
        "--goal",
        "capture regression target",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))
    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "regression target",
        "--store-dir",
        str(store_dir),
    )
    assert promote.returncode == 0, promote.stderr
    manifest_path = Path(get_str(parse_json(promote.stdout), "manifest_path"))

    regression = run_omf(
        "regress",
        str(manifest_path),
        "--source-artifact",
        str(evidence_path),
        "--name",
        "regression target",
        "--reason",
        " ",
        "--store-dir",
        str(store_dir),
    )

    assert regression.returncode != 0
    assert "Regression case reason must not be empty" in regression.stderr


def test_capture_with_failing_harness_check_cannot_be_promoted(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    check_path = tmp_path / "check_artifact.py"
    write_script(script_path, "artifact.txt", "actual")
    write_check_script(check_path, "artifact.txt", "different")
    store_dir = tmp_path / ".omf"

    capture = run_omf(
        "capture",
        "--goal",
        "capture failing harness",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--check",
        f"{sys.executable} {check_path}",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )

    assert capture.returncode == 0, capture.stderr
    capture_payload = parse_json(capture.stdout)
    evidence_path = Path(get_str(capture_payload, "evidence_path"))
    harness_results = [get_dict(result) for result in get_list(capture_payload, "harness_results")]
    assert get_str(capture_payload, "status") == "fail"
    assert get_str(harness_results[0], "status") == "fail"

    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "failing harness",
        "--store-dir",
        str(store_dir),
    )

    assert promote.returncode != 0
    assert "Only passing evidence" in promote.stderr


def test_capture_records_real_git_state(tmp_path: Path) -> None:
    script_path = tmp_path / "make_artifact.py"
    tracked_path = tmp_path / "tracked.txt"
    write_script(script_path, "artifact.txt", "git evidence")
    _ = tracked_path.write_text("before\n", encoding="utf-8")
    store_dir = tmp_path / ".omf"

    assert run_git(tmp_path, "init").returncode == 0
    assert run_git(tmp_path, "config", "user.email", "omf@example.invalid").returncode == 0
    assert run_git(tmp_path, "config", "user.name", "omf test").returncode == 0
    assert run_git(tmp_path, "add", "make_artifact.py", "tracked.txt").returncode == 0
    assert run_git(tmp_path, "commit", "-m", "initial").returncode == 0
    _ = tracked_path.write_text("after\n", encoding="utf-8")

    capture = run_omf(
        "capture",
        "--goal",
        "capture git state",
        "--command",
        f"{sys.executable} {script_path}",
        "--artifact",
        "artifact.txt",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )

    assert capture.returncode == 0, capture.stderr
    capture_payload = parse_json(capture.stdout)
    git_payload = get_dict(capture_payload["git"])
    changed_files = set(get_list(git_payload, "changed_files"))

    assert git_payload["is_repository"] is True
    assert git_payload["dirty"] is True
    assert get_str(git_payload, "head_sha")
    assert "tracked.txt" in changed_files
    assert "artifact.txt" in changed_files
    assert git_payload["diff_sha256"]


def test_promote_rejects_failed_evidence(tmp_path: Path) -> None:
    script_path = tmp_path / "fail.py"
    _ = script_path.write_text("raise SystemExit(3)\n", encoding="utf-8")
    store_dir = tmp_path / ".omf"

    capture = run_omf(
        "capture",
        "--goal",
        "capture failing command",
        "--command",
        f"{sys.executable} {script_path}",
        "--cwd",
        str(tmp_path),
        "--store-dir",
        str(store_dir),
    )
    assert capture.returncode == 0, capture.stderr
    evidence_path = Path(get_str(parse_json(capture.stdout), "evidence_path"))

    promote = run_omf(
        "promote",
        str(evidence_path),
        "--name",
        "failed capability",
        "--store-dir",
        str(store_dir),
    )

    assert promote.returncode != 0
    assert "Only passing evidence" in promote.stderr
