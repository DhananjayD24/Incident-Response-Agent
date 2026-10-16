"""
Pydantic schemas (request / response) for the order-service.
Separate from ORM models to decouple the API surface from the DB layer.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Customer ────────────────────────────────────────────────────────────────

class CustomerBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime


# ── Product ─────────────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    sku: str
    stock: int = 0


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime


# ── OrderItem ───────────────────────────────────────────────────────────────

class OrderItemBase(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1)
    unit_price: float


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: float
    subtotal: float
    product: Optional[ProductOut] = None


# ── Order ───────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    items: list[OrderItemCreate] = Field(min_length=1)
    notes: Optional[str] = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    status: str
    total_amount: float
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    customer: Optional[CustomerOut] = None
    items: list[OrderItemOut] = []


class OrderListOut(BaseModel):
    """Paginated list response."""
    total: int
    page: int
    page_size: int
    items: list[OrderOut]


# ── Admin / Failure injection ────────────────────────────────────────────────

class FailureConfig(BaseModel):
    """Payload for POST /admin/failure to toggle failure modes at runtime."""
    n_plus_one: Optional[bool] = None
    db_slow: Optional[bool] = None
    db_slow_seconds: Optional[float] = None
    high_cpu: Optional[bool] = None
    error_spike: Optional[bool] = None
    error_spike_rate: Optional[float] = None
    memory_leak: Optional[bool] = None
    reset: bool = False  # set True to clear all runtime overrides


class FailureStatus(BaseModel):
    n_plus_one: bool
    db_slow: bool
    db_slow_seconds: float
    high_cpu: bool
    error_spike: bool
    error_spike_rate: float
    memory_leak: bool


# ── Deployment ───────────────────────────────────────────────────────────────

class DeploymentCreate(BaseModel):
    """Payload to record a deployment event."""
    service: str
    version: str
    commit_sha: Optional[str] = None
    deployed_by: str = "scenarios-cli"
    notes: Optional[str] = None


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    version: str
    commit_sha: Optional[str] = None
    deployed_by: str
    deployed_at: datetime.datetime
    notes: Optional[str] = None

