"""Attach English and Arabic values to the seeded services and tasks.

The reference catalogue in ``app/data/service_catalog.py`` holds every service
and task in the three interface languages. This script finds the seeded rows
(by their French name, or by their French description/short title) and writes
``name_i18n``, ``title_i18n`` and ``description_i18n`` on them, so the API can
answer in the language selected in the UI.

Run it against the database the application uses:

    docker compose exec app python localize_services_tasks.py --dry-run
    docker compose exec app python localize_services_tasks.py

It is idempotent: rows already carrying the same translations are skipped, and
a second run changes nothing. ``--company`` limits the run to one company.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bson import ObjectId
from pymongo import UpdateOne

from app.data.service_catalog import normalize, service_for_name, task_for
from app.database import get_db
from config import VERSION


def _company_filter(db, wanted):
    if not wanted:
        return {}
    query = {"$or": [{"company_name": wanted}, {"code": wanted}]}
    try:
        query["$or"].append({"_id": ObjectId(wanted)})
    except Exception:
        pass
    company = db.companies.find_one(query)
    if not company:
        sys.exit(f"No company matched {wanted!r}.")
    print(f"Company: {company.get('company_name')} ({company['_id']})")
    return {"company_id": company["_id"]}


def _first_paragraph(text):
    return (text or "").split("\n\n")[0]


def _task_entry(task):
    """Catalogue entry of a stored task, or None when it is not seeded data."""
    entry = task_for(_first_paragraph(task.get("description")))
    if entry:
        return entry
    return task_for(task.get("title"))


def main():
    parser = argparse.ArgumentParser(
        description=f"Localize seeded services and tasks (Document Manager {VERSION})"
    )
    parser.add_argument("--company", help="company name, code or id")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="writes per bulk request (default 200)")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written without writing anything")
    args = parser.parse_args()

    db = get_db()
    query = _company_filter(db, args.company)
    now = datetime.now(timezone.utc)

    services_updated = tasks_updated = services_skipped = tasks_skipped = 0
    pending = []

    def add(collection_name, update):
        pending.append((collection_name, update))
        if len(pending) >= args.batch_size:
            write_pending()

    def write_pending():
        for collection_name in ("services", "tasks"):
            ops = [update for name, update in pending if name == collection_name]
            if ops and not args.dry_run:
                getattr(db, collection_name).bulk_write(ops, ordered=False)
        pending.clear()

    for service in db.services.find(query, {"name": 1, "name_i18n": 1}):
        entry = service_for_name(service.get("name"))
        if not entry:
            services_skipped += 1
            continue
        if service.get("name_i18n") == entry["name"] and service.get("name") == entry["name"]["fr"]:
            services_skipped += 1
            continue
        if not args.quiet:
            print(f"service  {entry['name']['fr']!r}")
        add(
            "services",
            UpdateOne(
                {"_id": service["_id"]},
                {"$set": {"name": entry["name"]["fr"],
                          "name_i18n": entry["name"],
                          "updated_at": now}},
            ),
        )
        services_updated += 1

    for task in db.tasks.find(query, {"title": 1, "description": 1, "title_i18n": 1}):
        entry = _task_entry(task)
        if not entry:
            tasks_skipped += 1
            continue
        description_fr = task.get("description") or ""
        if normalize(_first_paragraph(description_fr)) != normalize(entry["text"]["fr"]):
            # A locally edited description stays French as written.
            description_fr = entry["text"]["fr"]
        description_i18n = dict(entry["text"])
        description_i18n["fr"] = description_fr
        if task.get("title_i18n") == entry["title"]:
            tasks_skipped += 1
            continue
        if not args.quiet:
            print(f"task     {entry['title']['fr']!r}")
        add(
            "tasks",
            UpdateOne(
                {"_id": task["_id"]},
                {"$set": {"title_i18n": entry["title"],
                          "description_i18n": description_i18n,
                          "updated_at": now}},
            ),
        )
        tasks_updated += 1

    write_pending()

    verb = "would be" if args.dry_run else "were"
    print(
        f"\n{services_updated} service(s) and {tasks_updated} task(s) {verb} localized; "
        f"{services_skipped} service(s) and {tasks_skipped} task(s) skipped."
    )
    if args.dry_run:
        print("Dry run: nothing was written.")


if __name__ == "__main__":
    main()
