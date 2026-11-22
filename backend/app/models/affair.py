from datetime import datetime, timezone
from typing import Optional, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, model_validator


class AffairCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    affair_type: str = "individual"
    customer_id: str = Field(..., description="Customer (user) ID")
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    # Optional handling: the affair can be opened with services and an
    # assignee (employee or local manager) so activities are generated.
    assigned_to: Optional[str] = None
    service_ids: list[str] = []
    generate_activities: bool = True


class AffairUpdate(BaseModel):
    name: Optional[str] = None
    affair_type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class AffairResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    affair_type: str
    customer_id: str
    customer_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_role: Optional[str] = None
    service_ids: list[str] = []
    service_names: list[str] = []
    activity_count: int = 0
    completed_activity_count: int = 0
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_object_id(cls, data):
        if isinstance(data, dict):
            for key in ("_id", "customer_id", "assigned_to"):
                if key in data and isinstance(data[key], ObjectId):
                    data[key] = str(data[key])
            if "service_ids" in data and data["service_ids"]:
                data["service_ids"] = [
                    str(s) if isinstance(s, ObjectId) else s
                    for s in data["service_ids"]
                ]
        return data
