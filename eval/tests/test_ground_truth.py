"""
Tests for the evaluation ground-truth files (eval/ground_truth/*.json).

These checks guarantee that:
  * every file parses and has the required schema,
  * the `scenario` field matches the file name,
  * every scenario registered in scripts/scenarios.py has a ground-truth file
    (and vice versa) — so the evaluation harness can always score a scenario,
  * every scenario registered in the CLI is backed by a real scenario_* function.

Pure stdlib + pytest (scripts/scenarios.py is inspected via `ast`, not imported,
so httpx is not required to run this suite).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_DIR = REPO_ROOT / "eval" / "ground_truth"
SCENARIOS_CLI = REPO_ROOT / "scripts" / "scenarios.py"

REQUIRED_TOP_LEVEL_KEYS = {
    "scenario",
    "title",
    "description",
    "true_root_cause",
    "injected_by",
    "key_evidence_signals",
    "red_herrings",
    "recommended_fix",
    "rollback_target",
    "evaluation_checks",
}
REQUIRED_ROOT_CAUSE_KEYS = {"category", "component", "summary"}
REQUIRED_SIGNAL_KEYS = {"metric", "panel", "expected_behaviour", "direction"}
VALID_DIRECTIONS = {"up", "down", "stable", "stable_or_down"}

GROUND_TRUTH_FILES = sorted(GROUND_TRUTH_DIR.glob("*.json"))


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_cli_tree() -> ast.Module:
    return ast.parse(SCENARIOS_CLI.read_text(encoding="utf-8"))


def _cli_registry_names() -> set[str]:
    """Extract the keys of the SCENARIOS dict in scripts/scenarios.py via AST."""
    for node in _load_cli_tree().body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(t, ast.Name) and t.id == "SCENARIOS" for t in targets
            ):
                assert isinstance(node.value, ast.Dict), "SCENARIOS must be a dict literal"
                return {ast.literal_eval(k) for k in node.value.keys}
    raise AssertionError("SCENARIOS registry not found in scripts/scenarios.py")


def _cli_function_names() -> set[str]:
    return {
        node.name
        for node in ast.walk(_load_cli_tree())
        if isinstance(node, ast.FunctionDef)
    }


# ── tests ──────────────────────────────────────────────────────────────────────

def test_ground_truth_files_exist():
    assert GROUND_TRUTH_DIR.is_dir(), "eval/ground_truth directory is missing"
    names = {p.stem for p in GROUND_TRUTH_FILES}
    assert len(names) >= 6, f"expected ≥6 ground-truth files, found {sorted(names)}"


def test_every_cli_scenario_has_ground_truth_and_vice_versa():
    registry = _cli_registry_names()
    files = {p.stem for p in GROUND_TRUTH_FILES}
    assert registry == files, (
        f"scenarios in CLI but missing ground truth: {sorted(registry - files)}; "
        f"ground truth without CLI scenario: {sorted(files - registry)}"
    )


def test_every_cli_scenario_has_a_function():
    functions = _cli_function_names()
    missing = [name for name in _cli_registry_names() if f"scenario_{name}" not in functions]
    assert not missing, f"SCENARIOS entries without a scenario_* function: {missing}"


@pytest.mark.parametrize(
    "path", GROUND_TRUTH_FILES, ids=[p.stem for p in GROUND_TRUTH_FILES]
)
def test_ground_truth_schema(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))

    missing = REQUIRED_TOP_LEVEL_KEYS - set(data)
    assert not missing, f"{path.name}: missing top-level keys {sorted(missing)}"

    assert data["scenario"] == path.stem, (
        f"{path.name}: 'scenario' field {data['scenario']!r} does not match file name"
    )
    assert isinstance(data["title"], str) and data["title"].strip()
    assert isinstance(data["description"], str) and data["description"].strip()
    assert isinstance(data["injected_by"], str) and data["injected_by"].strip()
    assert isinstance(data["recommended_fix"], str) and data["recommended_fix"].strip()
    assert data["rollback_target"] is None or isinstance(data["rollback_target"], str)

    root_cause = data["true_root_cause"]
    rc_missing = REQUIRED_ROOT_CAUSE_KEYS - set(root_cause)
    assert not rc_missing, f"{path.name}: true_root_cause missing {sorted(rc_missing)}"
    for key in REQUIRED_ROOT_CAUSE_KEYS:
        assert isinstance(root_cause[key], str) and root_cause[key].strip(), (
            f"{path.name}: true_root_cause.{key} must be a non-empty string"
        )

    signals = data["key_evidence_signals"]
    assert isinstance(signals, list) and signals, (
        f"{path.name}: key_evidence_signals must be a non-empty list"
    )
    for i, signal in enumerate(signals):
        sig_missing = REQUIRED_SIGNAL_KEYS - set(signal)
        assert not sig_missing, f"{path.name}: signal[{i}] missing {sorted(sig_missing)}"
        assert signal["direction"] in VALID_DIRECTIONS, (
            f"{path.name}: signal[{i}] direction {signal['direction']!r} "
            f"not in {sorted(VALID_DIRECTIONS)}"
        )
        assert isinstance(signal["metric"], str) and signal["metric"].strip()
        assert isinstance(signal["expected_behaviour"], str) and signal["expected_behaviour"].strip()

    assert isinstance(data["red_herrings"], list), f"{path.name}: red_herrings must be a list"

    checks = data["evaluation_checks"]
    assert isinstance(checks, list) and checks, (
        f"{path.name}: evaluation_checks must be a non-empty list"
    )
    assert all(isinstance(c, str) and c.strip() for c in checks), (
        f"{path.name}: every evaluation_check must be a non-empty string"
    )
