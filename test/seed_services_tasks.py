#!/usr/bin/env python3
"""Seed the six services and their main tasks (Tâches principales).

Each service of the reference catalogue in ``backend/app/data/service_catalog.py``
becomes one service; each of its tasks becomes one task of that service. The
France text is stored in the base fields (a short ``title`` plus the full
instruction as ``description``) and the English and Arabic values travel with the
row in ``name_i18n`` / ``title_i18n`` / ``description_i18n``, so the demo follows
the language selected in the interface.

Matching is case-insensitive and checks both the stored title and description,
so running the script twice does not duplicate anything.

Examples
--------
    python test/seed_services_tasks.py --dry-run
    python test/seed_services_tasks.py
    python test/seed_services_tasks.py --company "Cabinet Service Express"

Run it from the repository root (it reads ``.env`` for ``MONGO_URI``); inside
the stack use ``docker compose exec -T app python ../test/seed_services_tasks.py``.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.data.service_catalog import SERVICES, normalize  # noqa: E402


def load_db():
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv(os.path.join(ROOT, ".env"))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI is not set (expected in .env or the environment).")
    return MongoClient(uri, serverSelectionTimeoutMS=10000)[
        uri.rsplit("/", 1)[-1].split("?")[0]
    ]


def select_companies(db, wanted):
    """Return the list of companies to seed.

    With ``wanted`` set, only the matching company is returned; otherwise every
    company in the database is returned so the demo data stays consistent across
    tenants (matching the behaviour of the other seed scripts).
    """
    if wanted:
        query = {"$or": [{"company_name": wanted}, {"code": wanted}]}
        try:
            from bson import ObjectId

            query["$or"].append({"_id": ObjectId(wanted)})
        except Exception:
            pass
        company = db.companies.find_one(query)
        if not company:
            sys.exit(f"No company matched {wanted!r}.")
        return [company]
    companies = list(db.companies.find({}).sort("company_name", 1))
    if not companies:
        sys.exit("No companies found; create one first or pass --company.")
    return companies


def main():
    parser = argparse.ArgumentParser(description="Seed services and their main tasks.")
    parser.add_argument("--company", help="company name, code or id")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        for service in SERVICES:
            print(f"{service['name']['fr']} ({len(service['tasks'])} tasks)")
            for task in service["tasks"]:
                print("  -", task["title"]["fr"])
        print("\nDry run: nothing was written.")
        return

    db = load_db()
    companies = select_companies(db, args.company)
    print(f"Database : {db.name}")
    print(f"Companies: {len(companies)}")

    total_services_created = total_services_updated = 0
    total_tasks_created = total_tasks_skipped = 0

    for company in companies:
        company_id = company["_id"]
        label = company.get("company_name") or str(company_id)

        admin = db.users.find_one(
            {"company_id": company_id, "role": "local_admin", "is_active": True},
            sort=[("created_at", 1)],
        )
        created_by = admin["_id"] if admin else None

        existing_services = list(db.services.find({"company_id": company_id}))
        by_name = {}
        for service in existing_services:
            for candidate in [service.get("name")] + list((service.get("name_i18n") or {}).values()):
                known = normalize(candidate)
                if known:
                    by_name.setdefault(known, service)
        now = datetime.now(timezone.utc)

        services_created = services_updated = 0
        tasks_created = tasks_skipped = 0

        for service in SERVICES:
            name = service["name"]
            existing = next(
                (by_name[key] for key in (normalize(value) for value in name.values()) if key in by_name),
                None,
            )

            if existing:
                service_id = existing["_id"]
                db.services.update_one(
                    {"_id": service_id},
                    {"$set": {"name": name["fr"], "name_i18n": name, "is_active": True,
                              "company_id": company_id, "updated_at": now}},
                )
                services_updated += 1
            else:
                service_id = db.services.insert_one({
                    "name": name["fr"],
                    "name_i18n": name,
                    "description": None,
                    "price": None,
                    "is_active": True,
                    "task_ids": [],
                    "company_id": company_id,
                    "created_at": now,
                    "updated_at": now,
                }).inserted_id
                services_created += 1

            task_ids = [t["_id"] for t in db.tasks.find(
                {"company_id": company_id, "service_id": service_id}, {"_id": 1})]
            known_keys = set()
            for task in db.tasks.find(
                {"company_id": company_id, "service_id": service_id},
                {"title": 1, "description": 1},
            ):
                known_keys.add(normalize(task.get("title")))
                known_keys.add(normalize((task.get("description") or "").split("\n\n")[0]))

            for task in service["tasks"]:
                title = task["title"]
                text = task["text"]
                if normalize(title["fr"]) in known_keys or normalize(text["fr"]) in known_keys:
                    tasks_skipped += 1
                    continue
                task_id = db.tasks.insert_one({
                    "title": title["fr"],
                    "title_i18n": title,
                    "description": text["fr"],
                    "description_i18n": text,
                    "status": "pending",
                    "service_id": service_id,
                    "company_id": company_id,
                    "created_by": created_by,
                    "created_at": now,
                    "updated_at": now,
                }).inserted_id
                task_ids.append(task_id)
                known_keys.add(normalize(title["fr"]))
                tasks_created += 1

            db.services.update_one(
                {"_id": service_id},
                {"$set": {"task_ids": task_ids, "updated_at": now}},
            )

        total_services_created += services_created
        total_services_updated += services_updated
        total_tasks_created += tasks_created
        total_tasks_skipped += tasks_skipped
        print(f"  {label}: services +{services_created}/~{services_updated}, tasks +{tasks_created}/~{tasks_skipped}")

    print(f"\nTotals — Services: {total_services_created} created, {total_services_updated} updated.")
    print(f"Totals — Tasks: {total_tasks_created} created, {total_tasks_skipped} already present.")


if __name__ == "__main__":
    main()
