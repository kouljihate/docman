from datetime import datetime
from typing import Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field


class CompanySettingsUpdate(BaseModel):
    """Fields a local admin can edit on their own company."""

    company_name: str = Field(..., min_length=1, max_length=120)
    slogan: str = ""
    logo: Optional[str] = None
    address: str = ""
    email: str = ""
    phone: str = ""
    social_links: Dict[str, str] = {}
    tax_id: str = ""


class CompanyCreate(BaseModel):
    """Platform-level company creation (main admin)."""

    company_name: str = Field(..., min_length=1, max_length=120)
    code: str = ""
    slogan: str = ""
    logo: Optional[str] = None
    address: str = ""
    email: str = ""
    phone: str = ""
    social_links: Dict[str, str] = {}
    tax_id: str = ""
    is_active: bool = True

    # Optional first local administrator for the company.
    admin_username: Optional[str] = None
    admin_email: Optional[EmailStr] = None
    admin_password: Optional[str] = Field(default=None, min_length=6)
    admin_full_name: Optional[str] = None


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    code: Optional[str] = None
    slogan: Optional[str] = None
    logo: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    tax_id: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyAdminCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class CompanyResponse(BaseModel):
    id: str = Field(alias="_id")
    company_name: str
    code: str = ""
    slogan: str = ""
    logo: Optional[str] = None
    address: str = ""
    email: str = ""
    phone: str = ""
    social_links: Dict[str, str] = {}
    tax_id: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True

    @classmethod
    def from_mongo(cls, doc: dict) -> "CompanyResponse":
        data = dict(doc)
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        return cls(**data)


# Backwards-compatible alias used by older imports.
CompanySettingsResponse = CompanyResponse
