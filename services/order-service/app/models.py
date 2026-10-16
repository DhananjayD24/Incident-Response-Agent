"""SQLAlchemy models for the order-service."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list[Order]] = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    stock: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order_items: Mapped[list[OrderItem]] = relationship(
        "OrderItem", back_populates="product"
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship("Order", back_populates="items")
    product: Mapped[Product] = relationship("Product", back_populates="order_items")


class Deployment(Base):
    """Audit log of every service deployment, used by scenarios and MCP tools."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    deployed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="scenarios-cli")
    deployed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

