"""
Tests for the order-service.

Strategy
--------
* Use pytest + httpx.TestClient (synchronous) against the FastAPI app.
* Swap out the real Postgres DB for a SQLite in-memory database so the tests
  run without Docker.  We override the `get_db` FastAPI dependency and the
  `engine`/`create_tables` references so the app never touches Postgres.
* All failure-injection flags are reset before each test.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Override DB *before* importing app modules that touch the engine ──────────
SQLITE_URL = "sqlite:///./test_orders.db"

_test_engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


# Patch database module so the app uses SQLite
import app.database as _db_module  # noqa: E402

_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSession


def _get_test_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


from app.database import get_db  # noqa: E402
from app.main import app          # noqa: E402
from app.models import Base       # noqa: E402

app.dependency_overrides[get_db] = _get_test_db


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)
    import os
    if os.path.exists("test_orders.db"):
        os.remove("test_orders.db")


@pytest.fixture(autouse=True)
def reset_failures():
    """Reset all runtime failure overrides before each test."""
    from app.config import clear_failure_flags
    clear_failure_flags()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


# ── Seed helpers ──────────────────────────────────────────────────────────────

def _make_customer(client) -> dict:
    from app.models import Customer
    db = _TestSession()
    c = Customer(
        id=uuid.uuid4(),
        name="Test User",
        email=f"test-{uuid.uuid4()}@example.com",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    db.close()
    return {"id": str(c.id), "email": c.email}


def _make_product(client) -> dict:
    from app.models import Product
    db = _TestSession()
    p = Product(
        id=uuid.uuid4(),
        name="Widget",
        price=9.99,
        sku=f"SKU-{uuid.uuid4().hex[:8].upper()}",
        stock=100,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    db.close()
    return {"id": str(p.id), "price": p.price}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert body["db"] == "ok"


class TestOrdersCRUD:
    def test_list_orders_empty(self, client):
        resp = client.get("/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    def test_create_order(self, client):
        customer = _make_customer(client)
        product = _make_product(client)

        payload = {
            "customer_id": customer["id"],
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 2,
                    "unit_price": product["price"],
                }
            ],
        }
        resp = client.post("/orders", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_id"] == customer["id"]
        assert len(body["items"]) == 1
        assert body["items"][0]["quantity"] == 2
        assert body["status"] == "pending"

    def test_get_order_by_id(self, client):
        customer = _make_customer(client)
        product = _make_product(client)

        create_resp = client.post(
            "/orders",
            json={
                "customer_id": customer["id"],
                "items": [{"product_id": product["id"], "quantity": 1, "unit_price": 5.00}],
            },
        )
        order_id = create_resp.json()["id"]

        get_resp = client.get(f"/orders/{order_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == order_id

    def test_get_order_not_found(self, client):
        resp = client.get(f"/orders/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_create_order_unknown_customer(self, client):
        product = _make_product(client)
        resp = client.post(
            "/orders",
            json={
                "customer_id": str(uuid.uuid4()),
                "items": [{"product_id": product["id"], "quantity": 1, "unit_price": 1.0}],
            },
        )
        assert resp.status_code == 422

    def test_list_orders_pagination(self, client):
        resp = client.get("/orders?page=1&page_size=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert len(body["items"]) <= 5


class TestFailureInjection:
    def test_get_failure_status(self, client):
        resp = client.get("/admin/failure")
        assert resp.status_code == 200
        body = resp.json()
        for key in ["n_plus_one", "db_slow", "high_cpu", "error_spike", "memory_leak"]:
            assert key in body

    def test_set_and_reset_failure(self, client):
        # Enable error_spike at 100 %
        resp = client.post(
            "/admin/failure",
            json={"error_spike": True, "error_spike_rate": 1.0},
        )
        assert resp.status_code == 200
        assert resp.json()["error_spike"] is True

        # Next data-plane request should 500
        resp2 = client.get("/orders")
        assert resp2.status_code == 500

        # Reset
        client.post("/admin/failure", json={"reset": True})
        resp3 = client.get("/orders")
        assert resp3.status_code == 200

    def test_n_plus_one_flag(self, client):
        customer = _make_customer(client)
        product = _make_product(client)
        client.post(
            "/orders",
            json={
                "customer_id": customer["id"],
                "items": [{"product_id": product["id"], "quantity": 1, "unit_price": 1.0}],
            },
        )
        client.post("/admin/failure", json={"n_plus_one": True})
        resp = client.get("/orders")
        assert resp.status_code == 200  # still works, just slower

        client.post("/admin/failure", json={"reset": True})

    def test_memory_leak_flag(self, client):
        from app.failures import _leak_store

        client.post("/admin/failure", json={"memory_leak": True})
        before = len(_leak_store)
        client.get("/orders")
        after = len(_leak_store)
        assert after > before

        client.post("/admin/failure", json={"reset": True})


class TestMetrics:
    def test_metrics_endpoint(self, client):
        # Hit a couple of endpoints to generate metrics
        client.get("/health")
        client.get("/orders")

        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text
        assert "app_info" in text
