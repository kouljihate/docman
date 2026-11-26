"""Give every company between three and seven employees.

Examples (inside the running stack):

    docker compose exec app python seed_employees.py --dry-run
    docker compose exec app python seed_employees.py --yes

Each company is topped up with ``local_employee`` accounts until it holds a
deterministic target of 3-7 employees (derived from the company's position, so
re-running never changes the target). Companies that already have enough
employees are left untouched, and usernames/e-mails are checked against the
whole database, so the script is safe to run again.

Every seeded employee uses the default password ``looklook``, the same one the
seeded local admins use.
"""
import argparse
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

try:  # when run as a file
    BASE_DIR = Path(__file__).resolve().parent
except NameError:  # when piped through stdin (python -)
    BASE_DIR = Path.cwd()
sys.path.insert(0, str(BASE_DIR))

from bcrypt import gensalt, hashpw

from app.database import get_db
from app.tenancy import LOCAL_EMPLOYEE
from seed_companies import FIRST_NAMES, LAST_NAMES, _slug

MIN_EMPLOYEES = 3
MAX_EMPLOYEES = 7
DEFAULT_PASSWORD = "looklook"
# Older rows stored the role before it was renamed.
LEGACY_EMPLOYEE = "employee"
EMPLOYEE_ROLES = (LOCAL_EMPLOYEE, LEGACY_EMPLOYEE)


def _target_for(index):
    """The number of employees the company at `index` should end up with."""
    span = MAX_EMPLOYEES - MIN_EMPLOYEES + 1
    return MIN_EMPLOYEES + index % span


def _name_for(seed):
    value = zlib.crc32(seed.encode("utf-8"))
    first = FIRST_NAMES[value % len(FIRST_NAMES)]
    last = LAST_NAMES[(value // len(FIRST_NAMES)) % len(LAST_NAMES)]
    return first, last


def _username_for(first, last):
    return f"{_slug(first)}.{_slug(last).replace('-', '')}"


def build_employees(company, how_many, taken, password_hash, created_by=None, now=None):
    """Build `how_many` employee documents for `company`.

    `taken` holds every username and e-mail already in use; the new values are
    added to it so later calls (and later companies) stay unique.
    """
    now = now or datetime.now(timezone.utc)
    slug = _slug(company["company_name"])
    documents = []

    for ordinal in range(how_many):
        first, last = _name_for(f"{slug}:{ordinal}")
        base = _username_for(first, last)
        username = base
        suffix = 2
        while username in taken or f"{username}@{slug}.ma" in taken:
            username = f"{base}{suffix}"
            suffix += 1
        email = f"{username}@{slug}.ma"
        taken.add(username)
        taken.add(email)

        value = zlib.crc32(f"{slug}:{ordinal}:phone".encode("utf-8"))
        document = {
            "username": username,
            "email": email,
            "password": password_hash,
            "role": LOCAL_EMPLOYEE,
            "full_name": f"{first} {last}",
            "phone": f"+212 6{value % 100_000_000:08d}",
            "is_active": True,
            "company_id": company["_id"],
            "created_at": now,
            "updated_at": now,
        }
        if created_by:
            document["created_by"] = created_by
        documents.append(document)
    return documents


def _main_admin_id(db):
    admin = db.users.find_one({"role": {"$in": ["main_admin", "admin"]}}, {"_id": 1})
    return admin["_id"] if admin else None


def _current_counts(db):
    rows = db.users.aggregate(
        [
            {"$match": {"role": {"$in": list(EMPLOYEE_ROLES)}}},
            {"$group": {"_id": "$company_id", "n": {"$sum": 1}}},
        ]
    )
    return {row["_id"]: row["n"] for row in rows}


def _seed(db, dry_run):
    companies = list(
        db.companies.find({}, {"company_name": 1}).sort("company_name", 1)
    )
    if not companies:
        print("No companies found; nothing to do.")
        return 0

    counts = _current_counts(db)
    taken = set()
    for user in db.users.find({}, {"username": 1, "email": 1}):
        if user.get("username"):
            taken.add(user["username"])
        if user.get("email"):
            taken.add(user["email"])

    created_by = _main_admin_id(db)
    now = datetime.now(timezone.utc)
    plans = []
    for index, company in enumerate(companies):
        target = _target_for(index)
        missing = max(0, target - counts.get(company["_id"], 0))
        plans.append((company, target, missing))

    total = sum(missing for _, _, missing in plans)
    print(f"Database : {db.name}")
    print(f"Companies: {len(companies)}")
    print(f"To insert: {total} employees across {sum(1 for _, _, m in plans if m)} companies")
    for company, target, missing in plans[:10]:
        label = company.get("company_name") or str(company["_id"])
        print(f"  {label}: {counts.get(company['_id'], 0)} -> {target} (+{missing})")
    if len(plans) > 10:
        print(f"  ... and {len(plans) - 10} more companies")
    if not total:
        print("Every company already has 3-7 employees.")
        return 0
    if dry_run:
        print("Dry run: nothing was written.")
        return 0

    # Every seeded employee shares the default password, so one hash is enough.
    password_hash = hashpw(DEFAULT_PASSWORD.encode("utf-8"), gensalt()).decode("utf-8")

    created = 0
    for company, _, missing in plans:
        if not missing:
            continue
        documents = build_employees(
            company, missing, taken, password_hash, created_by, now
        )
        db.users.insert_many(documents)
        created += len(documents)
        print(f"  {company.get('company_name')}: added {len(documents)}")
    print(f"Created {created} employees (password: {DEFAULT_PASSWORD}).")
    return created


def main():
    parser = argparse.ArgumentParser(
        description="Give every company three to seven employees"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--yes", action="store_true", help="Apply the change")
    args = parser.parse_args()

    if not (args.dry_run or args.yes):
        print("Nothing written. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    db = get_db()
    _seed(db, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
