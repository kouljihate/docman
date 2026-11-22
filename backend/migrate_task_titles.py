"""Shorten task titles and keep the full sentence as the description.

Every task whose title is a whole sentence (the seeded service tasks) gets a
short title extracted from it, and the original sentence is moved into the
description field.

Run it against the database the application uses:

    docker compose exec app python migrate_task_titles.py --dry-run
    docker compose exec app python migrate_task_titles.py

It is idempotent: tasks whose title is already short are skipped, so running it
twice changes nothing. ``--company`` limits the migration to one company;
``--max-chars`` changes the target title length.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bson import ObjectId

from app.database import get_db
from app.utils.task_title import MAX_TITLE_CHARS, plan_task_change
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


def main():
    parser = argparse.ArgumentParser(
        description=f"Shorten task titles (Document Manager {VERSION})"
    )
    parser.add_argument("--company", help="company name, code or id")
    parser.add_argument("--max-chars", type=int, default=MAX_TITLE_CHARS,
                        help=f"maximum short title length (default {MAX_TITLE_CHARS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the changes without writing them")
    args = parser.parse_args()

    db = get_db()
    query = _company_filter(db, args.company)
    now = datetime.now(timezone.utc)

    updated = skipped = 0
    for task in db.tasks.find(query, {"title": 1, "description": 1}):
        change = plan_task_change(task, max_chars=args.max_chars)
        if not change:
            skipped += 1
            continue
        short, description = change
        print(f"- {task.get('title')}")
        print(f"+ {short}")
        if not args.dry_run:
            db.tasks.update_one(
                {"_id": task["_id"]},
                {
                    "$set": {
                        "title": short,
                        "description": description,
                        "updated_at": now,
                    }
                },
            )
        updated += 1

    verb = "would be" if args.dry_run else "were"
    print(f"\n{updated} task(s) {verb} shortened, {skipped} already short.")
    if args.dry_run:
        print("Dry run: nothing was written.")


if __name__ == "__main__":
    main()
