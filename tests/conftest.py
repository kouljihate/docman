import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Configure before the app modules read their settings.
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/docmanager_test")
os.environ.setdefault("MONGO_HOST", "")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import app.database as database  # noqa: E402
from app import create_app  # noqa: E402

flask_app = create_app()
flask_app.config.update(TESTING=True)


@pytest.fixture()
def db(monkeypatch):
    """In-memory stand-in for MongoDB, reset for every test."""
    fake = mongomock.MongoClient().get_database("docmanager_test")
    monkeypatch.setattr(database, "db", fake)
    return fake


@pytest.fixture()
def client(db):
    with flask_app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def make_company(db):
    def _make(name="Acme", code="acme"):
        now = datetime.now(timezone.utc)
        company = {
            "_id": ObjectId(),
            "company_name": name,
            "code": code,
            "slogan": "",
            "logo": None,
            "address": "",
            "email": "",
            "phone": "",
            "social_links": {},
            "tax_id": "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        db.companies.insert_one(company)
        return company

    return _make


@pytest.fixture()
def make_user(db):
    def _make(role="customer", username="user", company_id=None):
        now = datetime.now(timezone.utc)
        user = {
            "_id": ObjectId(),
            "username": username,
            "email": f"{username}@example.com",
            "password": "x",
            "role": role,
            "full_name": username.title(),
            "phone": None,
            "is_active": True,
            "company_id": company_id,
            "created_at": now,
            "updated_at": now,
        }
        db.users.insert_one(user)
        return user

    return _make


@pytest.fixture()
def make_token():
    from flask_jwt_extended import create_access_token

    def _make(user):
        with flask_app.app_context():
            return create_access_token(
                identity=str(user["_id"]),
                additional_claims={
                    "role": user["role"],
                    "company_id": str(user["company_id"]) if user.get("company_id") else "",
                },
            )

    return _make
