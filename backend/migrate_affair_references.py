"""Give every existing affair its reference (``A`` + ``YYMMDD`` + ``-`` + ``HHMM``).

Affairs created before references existed get one derived from their creation
time, in the server's local time zone. Affairs that already have a reference
are left untouched, so the script can be run again safely.

    docker compose exec app python migrate_affair_references.py --dry-run
    docker compose exec app python migrate_affair_references.py
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bson import ObjectId

from app.database import get_db
from app.utils.affair_reference import next_reference
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


def _moment_for(affair):
    created_at = affair.get("created_at")
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at.astimezone()
    return datetime.now()


def main():
    parser = argparse.ArgumentParser(
        description=f"Backfill affair references (Document Manager {VERSION})"
    )
    parser.add_argument("--company", help="company name, code or id")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the references without writing them")
    args = parser.parse_args()

    db = get_db()
    query = _company_filter(db, args.company)
    query["$or"] = [{"reference": {"$exists": False}}, {"reference": None}]

    updated = 0
    for affair in db.affairs.find(query).sort("created_at", 1):
        reference = next_reference(db, affair.get("company_id"), _moment_for(affair))
        print(f"- {affair.get('name')}: {reference}")
        if not args.dry_run:
            db.affairs.update_one({"_id": affair["_id"]}, {"$set": {"reference": reference}})
        updated += 1

    verb = "would get" if args.dry_run else "got"
    print(f"\n{updated} affair(s) {verb} a reference.")
    if args.dry_run:
        print("Dry run: nothing was written.")


if __name__ == "__main__":
    main()
