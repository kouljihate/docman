"""Shared helpers for the operational scripts in ``backend/scripts``.

These scripts talk straight to the database, so they are meant to be run inside
the stack:

    docker compose exec app python scripts/add_users.py --help

They only need the backend directory on ``sys.path``; the container already
starts in ``/app/backend``.
"""
import argparse
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from bson import ObjectId
from bson.errors import InvalidId

from app.tenancy import CUSTOMER, LOCAL_ADMIN, LOCAL_EMPLOYEE
from config import DEFAULT_PASSWORD
from seed_companies import FIRST_NAMES, LAST_NAMES, _slug

# Roles a script may create; legacy names are mapped first.
MANAGED_ROLES = (LOCAL_ADMIN, LOCAL_EMPLOYEE, CUSTOMER)
LEGACY_ROLES = {
    "admin": LOCAL_ADMIN,
    "employee": LOCAL_EMPLOYEE,
}


def normalize_role(value):
    role = (value or "").strip().lower()
    return LEGACY_ROLES.get(role, role)


def parse_count(value):
    """Accept ``5`` or a range such as ``3-7`` (inclusive)."""
    text = str(value).strip()
    try:
        if "-" in text:
            low, _, high = text.partition("-")
            low, high = int(low), int(high)
            if low < 1 or high < low:
                raise ValueError
            return low, high
        number = int(text)
        if number < 1:
            raise ValueError
        return number, number
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"count must be a number or a range like 3-7, got {value!r}"
        )


def resolve_companies(db, reference=None):
    """All companies, or the one matching a name (case-insensitive) or id."""
    companies = list(
        db.companies.find({}, {"company_name": 1}).sort("company_name", 1)
    )
    if reference is None:
        return companies

    wanted = reference.strip().lower()
    matches = [
        company
        for company in companies
        if (company.get("company_name") or "").lower() == wanted
    ]
    if not matches:
        try:
            company_id = ObjectId(wanted)
        except (InvalidId, TypeError):
            company_id = None
        if company_id is not None:
            matches = [company for company in companies if company["_id"] == company_id]
    if not matches:
        raise SystemExit(f"No company matches {reference!r}.")
    return matches


def name_for(seed):
    value = zlib.crc32(seed.encode("utf-8"))
    first = FIRST_NAMES[value % len(FIRST_NAMES)]
    last = LAST_NAMES[(value // len(FIRST_NAMES)) % len(LAST_NAMES)]
    return first, last


def unique_username(first, last, slug, taken):
    base = f"{_slug(first)}.{_slug(last).replace('-', '')}"
    username, suffix = base, 2
    while username in taken or f"{username}@{slug}.ma" in taken:
        username = f"{base}{suffix}"
        suffix += 1
    taken.add(username)
    taken.add(f"{username}@{slug}.ma")
    return username


def taken_identifiers(db):
    taken = set()
    for user in db.users.find({}, {"username": 1, "email": 1}):
        if user.get("username"):
            taken.add(user["username"])
        if user.get("email"):
            taken.add(user["email"])
    return taken


def main_admin_id(db):
    admin = db.users.find_one({"role": {"$in": ["main_admin", "admin"]}}, {"_id": 1})
    return admin["_id"] if admin else None


def local_admin_id(db, company_id):
    """The company's earliest active local admin, used as a customer's owner."""
    admin = db.users.find_one(
        {"company_id": company_id, "role": LOCAL_ADMIN, "is_active": True},
        sort=[("created_at", 1)],
    )
    return admin["_id"] if admin else None


def build_users(
    db,
    company,
    role,
    how_many,
    taken,
    password_hash,
    created_by=None,
    now=None,
    seed=None,
):
    """Build `how_many` user documents of `role` for `company`."""
    now = now or datetime.now(timezone.utc)
    slug = _slug(company.get("company_name") or str(company["_id"]))
    documents = []

    for ordinal in range(how_many):
        seed_key = f"{seed or slug}:{role}:{ordinal}"
        first, last = name_for(seed_key)
        username = unique_username(first, last, slug, taken)
        value = zlib.crc32(f"{seed_key}:phone".encode("utf-8"))

        document = {
            "username": username,
            "email": f"{username}@{slug}.ma",
            "password": password_hash,
            "role": role,
            "full_name": f"{first} {last}",
            "phone": f"+212 6{value % 100_000_000:08d}",
            "is_active": True,
            "company_id": company["_id"],
            "created_at": now,
            "updated_at": now,
        }
        if created_by:
            document["created_by"] = created_by
        if role == CUSTOMER:
            document["local_admin_id"] = local_admin_id(db, company["_id"])
        documents.append(document)
    return documents


def collect_customer_cascade(db, customer_ids):
    """Ids of every row that belongs to the given customers."""
    if not customer_ids:
        return {
            "customers": [],
            "affairs": [],
            "activities": [],
            "documents": [],
            "payments": [],
        }

    affair_ids = [
        affair["_id"]
        for affair in db.affairs.find(
            {"customer_id": {"$in": customer_ids}}, {"_id": 1}
        )
    ]
    activity_query = {"customer_id": {"$in": customer_ids}}
    if affair_ids:
        activity_query = {
            "$or": [activity_query, {"affair_id": {"$in": affair_ids}}]
        }
    return {
        "customers": list(customer_ids),
        "affairs": affair_ids,
        "activities": [
            activity["_id"]
            for activity in db.activities.find(activity_query, {"_id": 1})
        ],
        "documents": [
            document["_id"]
            for document in db.documents.find(
                {"customer_id": {"$in": customer_ids}}, {"_id": 1}
            )
        ],
        "payments": [
            payment["_id"]
            for payment in db.payments.find(
                {"customer_id": {"$in": customer_ids}}, {"_id": 1}
            )
        ],
    }


def delete_customer_cascade(db, plan):
    """Delete the rows collected by :func:`collect_customer_cascade`."""
    if plan["activities"]:
        db.notifications.delete_many({"activity_id": {"$in": plan["activities"]}})
        db.activities.delete_many({"_id": {"$in": plan["activities"]}})
    if plan["affairs"]:
        db.affairs.delete_many({"_id": {"$in": plan["affairs"]}})
    if plan["documents"]:
        db.documents.delete_many({"_id": {"$in": plan["documents"]}})
    if plan["payments"]:
        db.payments.delete_many({"_id": {"$in": plan["payments"]}})
    db.users.delete_many({"_id": {"$in": plan["customers"]}})
