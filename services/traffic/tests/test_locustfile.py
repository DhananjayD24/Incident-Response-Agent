"""
Structural tests for the Locust traffic generator (services/traffic/locustfile.py).

The locustfile is inspected via `ast` instead of imported, so this suite runs
without the `locust` package installed.
"""
from __future__ import annotations

import ast
from pathlib import Path

TRAFFIC_DIR = Path(__file__).resolve().parents[1]
LOCUSTFILE = TRAFFIC_DIR / "locustfile.py"
DOCKERFILE = TRAFFIC_DIR / "Dockerfile"
REQUIREMENTS = TRAFFIC_DIR / "requirements.txt"

REQUIRED_ENDPOINTS = {"/health", "/orders"}


def _tree() -> ast.Module:
    return ast.parse(LOCUSTFILE.read_text(encoding="utf-8"))


def _user_class() -> ast.ClassDef:
    for node in _tree().body:
        if isinstance(node, ast.ClassDef):
            return node
    raise AssertionError("locustfile.py must define a user class")


def _task_weights() -> dict[str, int]:
    """Return {method_name: weight} for every @task-decorated method."""
    weights: dict[str, int] = {}
    for node in _user_class().body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Name)
                and dec.func.id == "task"
                and dec.args
            ):
                weights[node.name] = ast.literal_eval(dec.args[0])
    return weights


def test_locustfile_exists():
    assert LOCUSTFILE.is_file()


def test_user_class_has_wait_time_and_tasks():
    cls = _user_class()
    base_names = {
        base.id if isinstance(base, ast.Name) else ast.unparse(base)
        for base in cls.bases
    }
    assert "HttpUser" in base_names, (
        f"user class must subclass HttpUser, got bases {sorted(base_names)}"
    )
    assert any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "wait_time" for t in n.targets)
        for n in cls.body
    ), "user class must define wait_time (think time between requests)"

    weights = _task_weights()
    assert len(weights) >= 4, f"expected ≥4 weighted tasks, found {weights}"


def test_task_weights_are_positive_and_sum_to_100():
    weights = _task_weights()
    assert all(w > 0 for w in weights.values()), f"weights must be > 0: {weights}"
    assert sum(weights.values()) == 100, (
        f"task weights should sum to 100 for a readable mix, got {sum(weights.values())}"
    )


def test_traffic_mix_covers_expected_endpoints():
    cls = _user_class()
    literals = {
        node.value
        for node in ast.walk(cls)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for endpoint in REQUIRED_ENDPOINTS:
        assert endpoint in literals, f"locustfile never calls {endpoint}"

    client_calls: set[str] = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.Call):
            fn = ast.unparse(node.func)
            if ".client." in fn:
                client_calls.add(fn.rsplit(".", 1)[-1])
    assert "get" in client_calls, "traffic mix must include GET requests"
    assert "post" in client_calls, "traffic mix must include order creation (POST /orders)"


def test_requirements_pins_locust():
    content = REQUIREMENTS.read_text(encoding="utf-8")
    assert "locust" in content, "services/traffic/requirements.txt must include locust"


def test_dockerfile_copies_locustfile_and_defaults_to_headless():
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert "locustfile.py" in content
    assert "ENV LOCUST_HEADLESS=true" in content, (
        "container should send steady traffic by default (headless mode)"
    )
    assert "--headless" in content
