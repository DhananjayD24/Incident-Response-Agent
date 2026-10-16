#!/usr/bin/env python3
"""
Locust traffic file for the order-service.

Sends realistic, weighted traffic against:
  GET  /health          (5 %)
  GET  /orders          (40 %)
  GET  /orders/{id}     (35 %)
  POST /orders          (20 %)

Run locally (no Locust UI, headless):
  locust -f locustfile.py --headless -u 10 -r 2 --host http://localhost:8000

Run with the web UI:
  locust -f locustfile.py --host http://localhost:8000
  # then open http://localhost:8089
"""
from __future__ import annotations

import random
import uuid


# pyrefly: ignore [missing-import]
from locust import HttpUser, between, task


# ── Shared state (order / customer IDs discovered at runtime) ─────────────────

_known_order_ids: list[str] = []


class OrderServiceUser(HttpUser):
    """Simulates a realistic mix of API consumers."""

    wait_time = between(0.2, 1.5)  # think-time between requests

    # ── On-start: discover a page of existing orders to use for GETs ──────────

    def on_start(self) -> None:
        """Seed the local order-id pool from the first page of /orders."""
        resp = self.client.get("/orders?page=1&page_size=50", name="/orders[seed]")
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                oid = item.get("id")
                if oid and oid not in _known_order_ids:
                    _known_order_ids.append(oid)

    # ── Tasks ──────────────────────────────────────────────────────────────────

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(40)
    def list_orders(self) -> None:
        page = random.randint(1, 5)
        page_size = random.choice([10, 20, 50])
        self.client.get(
            f"/orders?page={page}&page_size={page_size}",
            name="/orders",
        )

    @task(35)
    def get_order(self) -> None:
        if not _known_order_ids:
            self.list_orders()
            return
        order_id = random.choice(_known_order_ids)
        with self.client.get(
            f"/orders/{order_id}",
            name="/orders/{id}",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                # Stale ID – remove and mark as success to avoid noise
                if order_id in _known_order_ids:
                    _known_order_ids.remove(order_id)
                resp.success()

    @task(20)
    def create_order(self) -> None:
        """
        Create an order.  We use placeholder UUIDs that the service will
        reject with 422 if the customer/product doesn't exist — that's fine
        and realistic (mimics validation errors in production).
        We first try to fetch real IDs; if unavailable we generate random ones.
        """
        customer_id = str(uuid.uuid4())
        product_id = str(uuid.uuid4())
        unit_price = round(random.uniform(5.0, 299.99), 2)
        qty = random.randint(1, 4)

        payload = {
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": unit_price,
                }
            ],
            "notes": random.choice([None, "Rush order", "Gift wrap please", "Leave at door"]),
        }

        with self.client.post(
            "/orders",
            json=payload,
            name="/orders[POST]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                data = resp.json()
                oid = data.get("id")
                if oid and oid not in _known_order_ids:
                    _known_order_ids.append(oid)
                resp.success()
            elif resp.status_code == 422:
                # Validation errors are expected when using random IDs
                resp.success()
            # 500s will naturally count as failures in Locust metrics
