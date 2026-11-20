"""Migrate a single-company database to the multi-company (tenant) model.

Run once after upgrading:

    docker compose exec app python migrate_tenancy.py
    python backend/migrate_tenancy.py --main-admin admin

What it does (idempotent):
- creates a default company from the legacy ``company_settings`` document,
- normalizes legacy roles (admin -> local_admin, employee -> local_employee),
- attaches every user and business document to the default company,
- routes existing customers to the company's first local administrator,
- optionally promotes one account to the platform ``main_admin``.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bson import ObjectId

from app.database import get_db
from config import VERSION

BUSINESS_COLLECTIONS = (
    "tasks",
    "activities",
    "affairs",
    "services",
    "documents",
    "notifications",
    "requests",
    "audit_logs",
)


def main():
    parser = argparse.ArgumentParser(description=f"Migrate Document Manager {VERSION} to multi-company")
    parser.add_argument("--main-admin", help="Username to promote to main_admin")
    parser.add_argument("--company-name", help="Name for the default company")
    args = parser.parse_args()

    db = get_db()
    now = datetime.now(timezone.utc)

    # 1. Legacy roles -> new profiles.
    renamed = 0
    for old, new in (("admin", "local_admin"), ("employee", "local_employee")):
        result = db.users.update_many({"role": old}, {"$set": {"role": new, "updated_at": now}})
        renamed += result.modified_count
    print(f"Roles normalized: {renamed}")

    # 2. Default company for pre-existing data.
    company = db.companies.find_one({"code": "default"}) or db.companies.find_one()
    if not company:
        legacy = db.company_settings.find_one() or {}
        company_name = args.company_name or legacy.get("company_name") or "Default Company"
        company = {
            "company_name": company_name,
            "code": "default",
            "slogan": legacy.get("slogan", ""),
            "logo": legacy.get("logo"),
            "address": legacy.get("address", ""),
            "email": legacy.get("email", ""),
            "phone": legacy.get("phone", ""),
            "social_links": legacy.get("social_links", {}),
            "tax_id": legacy.get("tax_id", ""),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        company["_id"] = db.companies.insert_one(company).inserted_id
        print(f"Default company created: {company_name} ({company['_id']})")
    else:
        print(f"Using existing company: {company.get('company_name')} ({company['_id']})")

    company_id = company["_id"]

    # 3. Attach users without a company.
    user_result = db.users.update_many(
        {"company_id": {"$exists": False}, "role": {"$in": ["local_admin", "local_employee", "customer"]}},
        {"$set": {"company_id": company_id, "updated_at": now}},
    )
    print(f"Users attached to the company: {user_result.modified_count}")

    local_admin = db.users.find_one({"company_id": company_id, "role": "local_admin"})
    if local_admin:
        routed = db.users.update_many(
            {"company_id": company_id, "role": "customer", "local_admin_id": {"$in": [None, ""]}},
            {"$set": {"local_admin_id": local_admin["_id"], "updated_at": now}},
        )
        print(f"Customers routed to {local_admin.get('username')}: {routed.modified_count}")

    # 4. Attach business documents.
    for collection in BUSINESS_COLLECTIONS:
        result = db[collection].update_many(
            {"company_id": {"$exists": False}}, {"$set": {"company_id": company_id}}
        )
        if result.modified_count:
            print(f"{collection}: {result.modified_count} documents attached")

    # 5. Optional platform administrator.
    if args.main_admin:
        target = db.users.find_one({"username": args.main_admin})
        if not target:
            print(f"ERROR: user '{args.main_admin}' not found")
            return 1
        db.users.update_one(
            {"_id": target["_id"]},
            {"$set": {"role": "main_admin", "company_id": None, "updated_at": now}},
        )
        print(f"Promoted '{args.main_admin}' to main_admin")
    elif not db.users.find_one({"role": "main_admin"}):
        print(
            "NOTE: no main_admin exists yet. Register a new platform account, or re-run with "
            "--main-admin <username> to promote one."
        )

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
