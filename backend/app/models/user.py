from datetime import datetime, timezone
from typing import Optional, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr, model_validator


# "admin"/"employee" are legacy aliases kept for older clients.
ROLE_VALUES = Literal[
    "main_admin", "local_admin", "local_employee", "customer", "admin", "employee"
]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: ROLE_VALUES = "customer"
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[ROLE_VALUES] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: str
    role: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_object_id(cls, data):
        if isinstance(data, dict):
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
        return data
