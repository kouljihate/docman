from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, model_validator


class PaymentCreate(BaseModel):
    customer_id: str
    label: Optional[str] = Field(default=None, max_length=200)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="MAD", max_length=8)
    due_date: datetime
    status: Literal["pending", "paid", "cancelled"] = "pending"
    method: Optional[str] = None
    notes: Optional[str] = None


class PaymentUpdate(BaseModel):
    customer_id: Optional[str] = None
    label: Optional[str] = None
    amount: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[Literal["pending", "paid", "cancelled"]] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: str = Field(alias="_id")
    company_id: Optional[str] = None
    customer_id: str
    customer_name: Optional[str] = None
    customer_username: Optional[str] = None
    label: Optional[str] = None
    amount: float
    currency: str = "MAD"
    due_date: datetime
    status: str = "pending"
    # "overdue" when a pending payment is past its due date.
    display_status: str = "pending"
    is_overdue: bool = False
    paid_at: Optional[datetime] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def convert_object_id(cls, data):
        if isinstance(data, dict):
            for key in ("_id", "company_id", "customer_id"):
                if key in data and isinstance(data[key], ObjectId):
                    data[key] = str(data[key])
        return data
