from datetime import datetime, timezone
from typing import Optional, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

PHOTO_ID_PREFIXES = ("data:image/", "http://", "https://", "/static/", "/uploads/")
MAX_PHOTO_ID_LENGTH = 900_000  # ~650 KB of image data as a base64 data URL


def _clean_photo_id(value):
    """Accept an ID-document image as a data URL or an http(s)/static URL."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(PHOTO_ID_PREFIXES):
        raise ValueError("Photo ID must be an image data URL or an http(s) URL")
    if len(value) > MAX_PHOTO_ID_LENGTH:
        raise ValueError("Photo ID is too large (max ~650 KB)")
    return value


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
    # Customer identity document (Morocco).
    cin: Optional[str] = Field(default=None, max_length=20)
    photo_id: Optional[str] = None

    @field_validator("photo_id")
    @classmethod
    def validate_photo_id(cls, value):
        return _clean_photo_id(value)

    @field_validator("cin")
    @classmethod
    def validate_cin(cls, value):
        if value is None:
            return None
        value = value.strip().upper()
        return value or None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[ROLE_VALUES] = None
    cin: Optional[str] = Field(default=None, max_length=20)
    photo_id: Optional[str] = None
    # Only the main admin may move a user to another company.
    company_id: Optional[str] = None

    @field_validator("photo_id")
    @classmethod
    def validate_photo_id(cls, value):
        return _clean_photo_id(value)

    @field_validator("cin")
    @classmethod
    def validate_cin(cls, value):
        if value is None:
            return None
        return value.strip().upper() or None


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
    cin: Optional[str] = None
    photo_id: Optional[str] = None
    company_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_object_id(cls, data):
        if isinstance(data, dict):
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
            if isinstance(data.get("company_id"), ObjectId):
                data["company_id"] = str(data["company_id"])
        return data
