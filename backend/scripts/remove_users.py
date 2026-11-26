"""Remove users of one role from one company or from every company.

Examples (inside the running stack):

    docker compose exec app python scripts/remove_users.py --role customer --dry-run
    docker compose exec app python scripts/remove_users.py --role customer --yes
    docker compose exec app python scripts/remove_users.py --role local_employee --company "Atlas Logistique" --yes

Customers are cascaded the way the per-customer delete endpoint does it, plus
the rows that would otherwise be orphaned: their affairs, the activities
generated from those affairs (or owned by the customer), the notifications of
those activities, their documents and their payments.

Staff accounts (``local_employee``, ``local_admin``) are removed on their own:
their history stays, and activities still assigned to them keep the stale
reference, exactly like deleting a user from the Users page.

Always preview with ``--dry-run`` first: this cannot be undone.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    CUSTOMER,
    LEGACY_ROLES,
    LOCAL_ADMIN,
    MANAGED_ROLES,
    collect_customer_cascade,
    delete_customer_cascade,
    normalize_role,
    resolve_companies,
)

from app.database import get_db

# Stored roles that normalize to the requested one.
STORED_ALIASES = {stored: role for stored, role in LEGACY_ROLES.items()}


def _stored_roles(role):
    return [role] + [stored for stored, mapped in STORED_ALIASES.items() if mapped == role]


def _remove_customers(db, company_ids, dry_run):
    customer_ids = [
        user["_id"]
        for user in db.users.find(
            {"role": CUSTOMER, "company_id": {"$in": company_ids}}, {"_id": 1}
        )
    ]
    plan = collect_customer_cascade(db, customer_ids)
    print(f"  customers   : {len(plan['customers'])}")
    print(f"  affairs     : {len(plan['affairs'])}")
    print(f"  activities  : {len(plan['activities'])}")
    print(f"  documents   : {len(plan['documents'])}")
    print(f"  payments    : {len(plan['payments'])}")

    if not plan["customers"]:
        print("No matching customers; nothing to do.")
        return 0
    if dry_run:
        for user in db.users.find(
            {"role": CUSTOMER, "company_id": {"$in": company_ids}}, {"username": 1}
        ).limit(5):
            print(f"  would remove {user.get('username')}")
        print("Dry run: nothing was deleted.")
        return 0

    delete_customer_cascade(db, plan)
    print(f"Removed {len(plan['customers'])} customers and their data.")
    return len(plan["customers"])


def _remove_staff(db, role, company_ids, dry_run):
    query = {"role": {"$in": _stored_roles(role)}, "company_id": {"$in": company_ids}}
    users = list(db.users.find(query, {"username": 1}))
    print(f"  accounts    : {len(users)}")

    if not users:
        print("No matching accounts; nothing to do.")
        return 0
    assigned = db.activities.count_documents(
        {"assigned_to": {"$in": [user["_id"] for user in users]}}
    )
    if assigned:
        print(f"  activities still assigned to them: {assigned} (left in place)")
    if role == LOCAL_ADMIN:
        print("  warning: these companies may be left without a local admin")

    if dry_run:
        for user in users[:5]:
            print(f"  would remove {user.get('username')}")
        print("Dry run: nothing was deleted.")
        return 0

    db.users.delete_many({"_id": {"$in": [user["_id"] for user in users]}})
    print(f"Removed {len(users)} {role} accounts.")
    return len(users)


def _run(db, role, company_ref, dry_run):
    companies = resolve_companies(db, company_ref)
    if not companies:
        print("No companies found; nothing to do.")
        return 0

    print(f"Database  : {db.name}")
    print(f"Role      : {role}")
    print(f"Companies : {len(companies)}")
    for company in companies[:5]:
        print(f"  {company.get('company_name')}")
    if len(companies) > 5:
        print(f"  ... and {len(companies) - 5} more companies")

    company_ids = [company["_id"] for company in companies]
    if role == CUSTOMER:
        return _remove_customers(db, company_ids, dry_run)
    return _remove_staff(db, role, company_ids, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="Remove users of one role from a company or from every company"
    )
    parser.add_argument(
        "--role",
        required=True,
        help="customer, local_employee or local_admin (legacy employee/admin accepted)",
    )
    parser.add_argument(
        "--company",
        help="Company name or id (default: every company)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    parser.add_argument("--yes", action="store_true", help="Apply the removal")
    args = parser.parse_args()

    role = normalize_role(args.role)
    if role not in MANAGED_ROLES:
        parser.error(f"--role must be one of: {', '.join(MANAGED_ROLES)}")

    if not (args.dry_run or args.yes):
        print("Nothing deleted. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    return _run(get_db(), role, args.company, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
