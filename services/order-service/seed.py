#!/usr/bin/env python3
"""
Seed script: generates realistic fake data using Faker.
  - ~1,000 customers
  - ~100 products
  - ~5,000 orders
  - ~20,000 order items (4 items on average per order)

Run inside the container:
  docker compose exec app python seed.py

Or locally (with DATABASE_URL set):
  python seed.py
"""
from __future__ import annotations

import os
import random
import sys
import uuid
from decimal import Decimal

# Allow running from the services/order-service directory without installing
sys.path.insert(0, os.path.dirname(__file__))

from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Customer, Order, OrderItem, Product

faker = Faker()
random.seed(42)
Faker.seed(42)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://orders:orders@localhost:5432/orders"
)

N_CUSTOMERS = 1_000
N_PRODUCTS = 100
N_ORDERS = 5_000
AVG_ITEMS_PER_ORDER = 4  # total items ≈ 20,000

STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
STATUS_WEIGHTS = [0.10, 0.15, 0.20, 0.45, 0.10]


def create_customers(session) -> list[Customer]:
    print(f"Creating {N_CUSTOMERS} customers…")
    emails: set[str] = set()
    customers: list[Customer] = []
    while len(customers) < N_CUSTOMERS:
        email = faker.unique.email()
        if email in emails:
            continue
        emails.add(email)
        customers.append(
            Customer(
                id=uuid.uuid4(),
                name=faker.name(),
                email=email,
                phone=faker.phone_number()[:50],
                address=faker.address().replace("\n", ", "),
            )
        )
    session.bulk_save_objects(customers)
    session.commit()
    print(f"  ✓ {len(customers)} customers inserted")
    return customers


def create_products(session) -> list[Product]:
    print(f"Creating {N_PRODUCTS} products…")
    categories = [
        "Electronics", "Clothing", "Books", "Home & Garden",
        "Sports", "Toys", "Food", "Beauty", "Automotive", "Office",
    ]
    products: list[Product] = []
    skus: set[str] = set()
    for i in range(N_PRODUCTS):
        sku = f"SKU-{faker.bothify('??##??##').upper()}"
        while sku in skus:
            sku = f"SKU-{faker.bothify('??##??##').upper()}"
        skus.add(sku)
        cat = random.choice(categories)
        products.append(
            Product(
                id=uuid.uuid4(),
                name=f"{faker.word().capitalize()} {cat} {faker.word().capitalize()}",
                description=faker.sentence(nb_words=12),
                price=float(round(random.uniform(2.99, 499.99), 2)),
                sku=sku,
                stock=random.randint(0, 500),
            )
        )
    session.bulk_save_objects(products)
    session.commit()
    print(f"  ✓ {len(products)} products inserted")
    return products


def create_orders_and_items(
    session,
    customers: list[Customer],
    products: list[Product],
) -> None:
    print(f"Creating {N_ORDERS} orders with ~{AVG_ITEMS_PER_ORDER} items each…")
    orders: list[Order] = []
    items: list[OrderItem] = []

    for i in range(N_ORDERS):
        customer = random.choice(customers)
        status = random.choices(STATUSES, STATUS_WEIGHTS)[0]
        order_id = uuid.uuid4()
        n_items = max(1, int(random.gauss(AVG_ITEMS_PER_ORDER, 1.5)))

        order_total = 0.0
        order_items: list[OrderItem] = []
        chosen_products = random.sample(products, min(n_items, len(products)))
        for product in chosen_products:
            qty = random.randint(1, 5)
            unit_price = float(round(product.price * random.uniform(0.9, 1.1), 2))
            subtotal = round(unit_price * qty, 2)
            order_total += subtotal
            order_items.append(
                OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=unit_price,
                    subtotal=subtotal,
                )
            )

        orders.append(
            Order(
                id=order_id,
                customer_id=customer.id,
                status=status,
                total_amount=round(order_total, 2),
                notes=faker.sentence() if random.random() < 0.3 else None,
            )
        )
        items.extend(order_items)

        # Flush in batches to keep memory manageable
        if len(orders) % 500 == 0:
            session.bulk_save_objects(orders)
            session.bulk_save_objects(items)
            session.commit()
            print(f"  … {i + 1}/{N_ORDERS} orders committed")
            orders.clear()
            items.clear()

    if orders:
        session.bulk_save_objects(orders)
        session.bulk_save_objects(items)
        session.commit()

    print(f"  ✓ {N_ORDERS} orders and ~{N_ORDERS * AVG_ITEMS_PER_ORDER} items inserted")


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        # Idempotency guard – skip if data already exists
        from sqlalchemy import text
        count = session.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        if count and count > 0:
            print(f"Database already seeded ({count} customers). Skipping.")
            return

        customers = create_customers(session)
        products = create_products(session)
        create_orders_and_items(session, customers, products)

    print("\n✅ Seeding complete!")


if __name__ == "__main__":
    main()
