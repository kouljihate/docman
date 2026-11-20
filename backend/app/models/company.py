import re
from datetime import datetime
from typing import Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator

# Moroccan company identifiers.
ICE_PATTERN = re.compile(r"^\d{15}$")
ICE_HINT = "ICE must contain exactly 15 digits"

LOGO_PREFIXES = ("data:image/", "http://", "https://", "/static/", "/uploads/")
MAX_LOGO_LENGTH = 900_000  # ~650 KB of image data as a base64 data URL

LEGAL_FORMS = (
    "SARL",
    "SARL AU",
    "SA",
    "SAS",
    "SNC",
    "SCS",
    "Auto-entrepreneur",
    "Association",
    "Coopérative",
    "Succursale",
    "Autre",
)


def _clean_logo(value):
    """Accept an image data URL or an http(s)/static URL, and cap its size."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(LOGO_PREFIXES):
        raise ValueError("Logo must be an image data URL or an http(s) URL")
    if len(value) > MAX_LOGO_LENGTH:
        raise ValueError("Logo is too large (max ~650 KB)")
    return value


def _clean_ice(value):
    if value is None:
        return ""
    value = value.strip()
    if not value:
        return ""
    if not ICE_PATTERN.match(value):
        raise ValueError(ICE_HINT)
    return value


class _CompanyProfileValidators(BaseModel):
    """Shared normalisation for the Moroccan company fields on input models."""

    @field_validator("logo", check_fields=False)
    @classmethod
    def _validate_logo(cls, value):
        return _clean_logo(value)

    @field_validator("ice", check_fields=False)
    @classmethod
    def _validate_ice(cls, value):
        return _clean_ice(value)


class CompanySettingsUpdate(_CompanyProfileValidators):
    """Fields a local admin can edit on their own company."""

    company_name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = None
    slogan: Optional[str] = None
    logo: Optional[str] = None
    legal_form: Optional[str] = None
    ice: Optional[str] = None
    rc: Optional[str] = None
    tax_id: Optional[str] = None
    patente: Optional[str] = None
    cnss: Optional[str] = None
    capital: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None


class CompanyCreate(_CompanyProfileValidators):
    """Platform-level company creation (main admin)."""

    company_name: str = Field(..., min_length=1, max_length=120)
    code: str = ""
    slogan: str = ""
    logo: Optional[str] = None
    # Moroccan legal identification.
    legal_form: str = ""
    ice: str = ""
    rc: str = ""
    tax_id: str = ""
    patente: str = ""
    cnss: str = ""
    capital: str = ""
    # Address.
    address: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country: str = "Maroc"
    # Contact.
    email: str = ""
    phone: str = ""
    website: str = ""
    social_links: Dict[str, str] = {}
    is_active: bool = True

    # Optional first local administrator for the company.
    admin_username: Optional[str] = None
    admin_email: Optional[EmailStr] = None
    admin_password: Optional[str] = Field(default=None, min_length=6)
    admin_full_name: Optional[str] = None


class CompanyUpdate(_CompanyProfileValidators):
    company_name: Optional[str] = None
    code: Optional[str] = None
    slogan: Optional[str] = None
    logo: Optional[str] = None
    legal_form: Optional[str] = None
    ice: Optional[str] = None
    rc: Optional[str] = None
    tax_id: Optional[str] = None
    patente: Optional[str] = None
    cnss: Optional[str] = None
    capital: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
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
    legal_form: str = ""
    ice: str = ""
    rc: str = ""
    tax_id: str = ""
    patente: str = ""
    cnss: str = ""
    capital: str = ""
    address: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country: str = "Maroc"
    email: str = ""
    phone: str = ""
    website: str = ""
    social_links: Dict[str, str] = {}
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
        # Ignore any legacy/unexpected keys instead of failing the response.
        allowed = set(cls.model_fields.keys()) | {"_id"}
        data = {k: v for k, v in data.items() if k in allowed}
        return cls(**data)


# Backwards-compatible alias used by older imports.
CompanySettingsResponse = CompanyResponse
