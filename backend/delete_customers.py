"""Remove every customer account and its data from the Document Manager database.

Examples (inside the running stack):

    docker compose exec app python delete_customers.py --dry-run
    docker compose exec app python delete_customers.py --yes

Only accounts whose role is ``customer`` are touched; staff and platform
accounts are never removed. Each customer is cascaded the same way the
per-customer delete endpoint does it, plus the dependent rows that would
otherwise be orphaned: their affairs, the activities generated from those
affairs (or owned by the customer), the notifications of those activities,
their documents and their payments.

Always preview with ``--dry-run`` first: this cannot be undone.
"""
import argparse
import sys
from pathlib import Path

try:  # when run as a file
    BASE_DIR = Path(__file__).resolve().parent
except NameError:  # when piped through stdin (python -)
    BASE_DIR = Path.cwd()
sys.path.insert(0, str(BASE_DIR))

from app.database import get_db
from app.tenancy import CUSTOMER


def _ids(cursor):
    return [document["_id"] for document in cursor]


def _collect(db):
    """Return the ids to delete, grouped by collection."""
    customer_ids = _ids(db.users.find({"role": CUSTOMER}, {"_id": 1}))
    if not customer_ids:
        return {
            "customers": [],
            "affairs": [],
            "activities": [],
            "documents": [],
            "payments": [],
        }

    affair_ids = _ids(
        db.affairs.find({"customer_id": {"$in": customer_ids}}, {"_id": 1})
    )
    activity_query = {"customer_id": {"$in": customer_ids}}
    if affair_ids:
        activity_query = {
            "$or": [
                activity_query,
                {"affair_id": {"$in": affair_ids}},
            ]
        }
    activity_ids = _ids(db.activities.find(activity_query, {"_id": 1}))
    document_ids = _ids(
        db.documents.find({"customer_id": {"$in": customer_ids}}, {"_id": 1})
    )
    payment_ids = _ids(
        db.payments.find({"customer_id": {"$in": customer_ids}}, {"_id": 1})
    )
    return {
        "customers": customer_ids,
        "affairs": affair_ids,
        "activities": activity_ids,
        "documents": document_ids,
        "payments": payment_ids,
    }


def _run(db, dry_run):
    plan = _collect(db)
    customers = plan["customers"]
    print(f"Database : {db.name}")
    print(f"Customers to remove : {len(customers)}")
    print(f"  affairs     : {len(plan['affairs'])}")
    print(f"  activities  : {len(plan['activities'])}")
    print(f"  documents   : {len(plan['documents'])}")
    print(f"  payments    : {len(plan['payments'])}")

    if not customers:
        print("No customers found; nothing to do.")
        return 0
    if dry_run:
        for customer in db.users.find({"role": CUSTOMER}, {"username": 1}).limit(5):
            print(f"  would remove {customer.get('username')}")
        print("Dry run: nothing was deleted.")
        return 0

    # Delete the dependent rows first so a failure never leaves a customer
    # without their history or history without its customer.
    if plan["activities"]:
        activity_ids = plan["activities"]
        db.notifications.delete_many({"activity_id": {"$in": activity_ids}})
        db.activities.delete_many({"_id": {"$in": activity_ids}})
    if plan["affairs"]:
        db.affairs.delete_many({"_id": {"$in": plan["affairs"]}})
    if plan["documents"]:
        db.documents.delete_many({"_id": {"$in": plan["documents"]}})
    if plan["payments"]:
        db.payments.delete_many({"_id": {"$in": plan["payments"]}})
    db.users.delete_many({"_id": {"$in": customers}})

    print(f"Removed {len(customers)} customers and their data.")
    return len(customers)


def main():
    parser = argparse.ArgumentParser(
        description="Remove every customer account and its data"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    parser.add_argument("--yes", action="store_true", help="Apply the removal")
    args = parser.parse_args()

    if not (args.dry_run or args.yes):
        print("Nothing deleted. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    db = get_db()
    _run(db, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
