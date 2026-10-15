"""
Order CRUD – queries that back GET /orders, GET /orders/{id}, POST /orders.

Two query strategies for listing orders are implemented:
  - Normal: single JOIN query loading items + customer eagerly.
  - N+1:    fetch orders first, then one query per order for its items
            (simulates the classic N+1 bug for observability demos).
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload, joinedload

from app import metrics as m
from app.config import get_failure_flag
from app.failures import maybe_db_slow
from app.models import Customer, Order, OrderItem, Product
from app.schemas import OrderCreate


# ── Helpers ──────────────────────────────────────────────────────────────────

def _track_query(endpoint: str, operation: str, fn, *args, **kwargs):
    """Run `fn(*args, **kwargs)`, recording DB query count + duration."""
    m.DB_QUERY_COUNT.labels(endpoint=endpoint, operation=operation).inc()
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    m.DB_QUERY_DURATION.labels(endpoint=endpoint, operation=operation).observe(
        time.perf_counter() - start
    )
    return result


# ── Read ─────────────────────────────────────────────────────────────────────

def list_orders(
    db: Session,
    endpoint: str = "/orders",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Order], int]:
    """
    Return a page of orders.

    When N_PLUS_ONE is active: load items for each order with a separate query.
    Otherwise: use a single eager-loading query with joinedload.
    """
    maybe_db_slow(db)

    offset = (page - 1) * page_size

    # Count query
    total = _track_query(
        endpoint,
        "count_orders",
        lambda: db.scalar(select(func.count()).select_from(Order)),
    )

    if get_failure_flag("n_plus_one"):
        # ── N+1 path ──────────────────────────────────────────────────────
        orders = _track_query(
            endpoint,
            "list_orders_n1",
            lambda: db.scalars(
                select(Order)
                .options(joinedload(Order.customer))
                .order_by(Order.created_at.desc())
                .offset(offset)
                .limit(page_size)
            ).unique().all(),
        )
        for order in orders:
            # One extra query per order — the N+1
            _track_query(
                endpoint,
                "fetch_items_n1",
                lambda o=order: db.scalars(
                    select(OrderItem)
                    .options(joinedload(OrderItem.product))
                    .where(OrderItem.order_id == o.id)
                ).all(),
            )
            # Access the lazily-loaded relationship to attach items in memory
            # (SQLAlchemy will use the separately fetched rows)
            _ = order.items
    else:
        # ── Efficient path: single query with joined loads ─────────────────
        orders = _track_query(
            endpoint,
            "list_orders",
            lambda: db.scalars(
                select(Order)
                .options(
                    joinedload(Order.customer),
                    selectinload(Order.items).joinedload(OrderItem.product),
                )
                .order_by(Order.created_at.desc())
                .offset(offset)
                .limit(page_size)
            ).unique().all(),
        )

    return list(orders), total


def get_order(db: Session, order_id: uuid.UUID, endpoint: str = "/orders/{id}") -> Optional[Order]:
    maybe_db_slow(db)
    return _track_query(
        endpoint,
        "get_order",
        lambda: db.scalar(
            select(Order)
            .options(
                joinedload(Order.customer),
                selectinload(Order.items).joinedload(OrderItem.product),
            )
            .where(Order.id == order_id)
        ),
    )


def create_order(db: Session, payload: OrderCreate, endpoint: str = "/orders") -> Order:
    maybe_db_slow(db)

    # Verify customer exists
    customer = _track_query(
        endpoint,
        "get_customer",
        lambda: db.get(Customer, payload.customer_id),
    )
    if not customer:
        raise ValueError(f"Customer {payload.customer_id} not found")

    order = Order(
        customer_id=payload.customer_id,
        status="pending",
        notes=payload.notes,
        total_amount=0,
    )
    db.add(order)
    db.flush()  # populate order.id

    total = 0.0
    for item_in in payload.items:
        product = _track_query(
            endpoint,
            "get_product",
            lambda pid=item_in.product_id: db.get(Product, pid),
        )
        if not product:
            raise ValueError(f"Product {item_in.product_id} not found")
        subtotal = item_in.unit_price * item_in.quantity
        total += subtotal
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=item_in.product_id,
                quantity=item_in.quantity,
                unit_price=item_in.unit_price,
                subtotal=subtotal,
            )
        )

    order.total_amount = total
    _track_query(endpoint, "commit_order", db.commit)
    db.refresh(order)

    # Re-load with relationships
    return get_order(db, order.id, endpoint=endpoint)
