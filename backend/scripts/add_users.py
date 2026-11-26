"""Add users of one role to one company or to every company.

Examples (inside the running stack):

    docker compose exec app python scripts/add_users.py --role local_employee --count 3-7 --dry-run
    docker compose exec app python scripts/add_users.py --role local_employee --count 3-7 --yes
    docker compose exec app python scripts/add_users.py --role customer --count 5 --company "Atlas Logistique" --yes

``--count`` takes a number or an inclusive range (``3-7``); a range gives every
company a deterministic target inside it. The command always *adds* that many
accounts, so run it once per top-up. Every created account gets the default
password ``looklook``, unique usernames and e-mails, and the company's owning
local admin when a customer is created.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bcrypt import gensalt, hashpw

from _common import (
    DEFAULT_PASSWORD,
    MANAGED_ROLES,
    build_users,
    main_admin_id,
    normalize_role,
    parse_count,
    resolve_companies,
    taken_identifiers,
)

from app.database import get_db


def _targets(low, high, count):
    """One target per company index inside the inclusive range."""
    span = high - low + 1
    return [low + index % span for index in range(count)]


def _run(db, role, low, high, company_ref, dry_run):
    companies = resolve_companies(db, company_ref)
    if not companies:
        print("No companies found; nothing to do.")
        return 0

    targets = _targets(low, high, len(companies))
    total = sum(targets)
    print(f"Database  : {db.name}")
    print(f"Role      : {role}")
    print(f"Companies : {len(companies)}")
    print(f"To create : {total} accounts")
    for company, target in list(zip(companies, targets))[:10]:
        print(f"  {company.get('company_name')}: +{target}")
    if len(companies) > 10:
        print(f"  ... and {len(companies) - 10} more companies")

    if dry_run:
        print("Dry run: nothing was written.")
        return 0

    now = datetime.now(timezone.utc)
    created_by = main_admin_id(db)
    taken = taken_identifiers(db)
    # Every created account shares the default password, so one hash is enough.
    password_hash = hashpw(DEFAULT_PASSWORD.encode("utf-8"), gensalt()).decode("utf-8")

    created = 0
    for company, target in zip(companies, targets):
        documents = build_users(
            db, company, role, target, taken, password_hash, created_by, now
        )
        if documents:
            db.users.insert_many(documents)
            created += len(documents)
            print(f"  {company.get('company_name')}: added {len(documents)}")
    print(f"Created {created} {role} accounts (password: {DEFAULT_PASSWORD}).")
    return created


def main():
    parser = argparse.ArgumentParser(
        description="Add users of one role to a company or to every company"
    )
    parser.add_argument(
        "--role",
        required=True,
        help="local_employee, customer or local_admin (legacy employee/admin accepted)",
    )
    parser.add_argument(
        "--count",
        type=parse_count,
        default=(1, 1),
        help="How many per company, or an inclusive range like 3-7 (default: 1)",
    )
    parser.add_argument(
        "--company",
        help="Company name or id (default: every company)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--yes", action="store_true", help="Apply the change")
    args = parser.parse_args()

    role = normalize_role(args.role)
    if role not in MANAGED_ROLES:
        parser.error(f"--role must be one of: {', '.join(MANAGED_ROLES)}")

    if not (args.dry_run or args.yes):
        print("Nothing written. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    low, high = args.count
    return _run(get_db(), role, low, high, args.company, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
