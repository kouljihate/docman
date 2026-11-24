"""Create test companies in the Document Manager database.

Examples (inside the running stack):

    docker compose exec app python seed_companies.py --dry-run
    docker compose exec app python seed_companies.py --yes
    docker compose exec app python seed_companies.py --count 25 --yes
    docker compose exec app python seed_companies.py --prefix "Demo" --yes
    docker compose exec app python seed_companies.py --delete --yes

Companies are named ``Test Company 001`` ... so they are easy to recognise and
easy to remove. Names that already exist are skipped, so re-running is safe.

``--delete`` removes only companies whose name starts with the prefix, together
with every document that carries their ``company_id``.
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # when run as a file
    BASE_DIR = Path(__file__).resolve().parent
except NameError:  # when piped through stdin (python -)
    BASE_DIR = Path.cwd()
sys.path.insert(0, str(BASE_DIR))

from app.database import get_db

DEFAULT_PREFIX = "Test Company"
DEFAULT_COUNT = 100

LEGAL_FORMS = (
    "SARL",
    "SARL AU",
    "SA",
    "SAS",
    "SNC",
    "Auto-entrepreneur",
    "Coopérative",
)

# (city, region, postal code)
LOCATIONS = (
    ("Casablanca", "Casablanca-Settat", "20000"),
    ("Rabat", "Rabat-Salé-Kénitra", "10000"),
    ("Marrakech", "Marrakech-Safi", "40000"),
    ("Fès", "Fès-Meknès", "30000"),
    ("Tanger", "Tanger-Tétouan-Al Hoceïma", "90000"),
    ("Agadir", "Souss-Massa", "80000"),
    ("Meknès", "Fès-Meknès", "50000"),
    ("Oujda", "Oriental", "60000"),
    ("Kénitra", "Rabat-Salé-Kénitra", "14000"),
    ("Tétouan", "Tanger-Tétouan-Al Hoceïma", "93000"),
)


def build_companies(count=DEFAULT_COUNT, prefix=DEFAULT_PREFIX, created_by=None, now=None):
    """Deterministically build ``count`` company documents."""
    now = now or datetime.now(timezone.utc)
    companies = []
    for n in range(1, count + 1):
        city, region, postal_code = LOCATIONS[(n - 1) % len(LOCATIONS)]
        company = {
            "company_name": f"{prefix} {n:03d}",
            "code": f"TC{n:03d}",
            "slogan": "Test tenant for platform checks",
            "logo": None,
            "legal_form": LEGAL_FORMS[(n - 1) % len(LEGAL_FORMS)],
            # 15 digits, unique per company.
            "ice": f"{100_000_000_000_000 + n}",
            "rc": f"RC-{10_000 + n}",
            "tax_id": f"{40_000_000 + n}",
            "patente": f"{5_000_000 + n}",
            "cnss": f"{800_000 + n}",
            "capital": "100 000 MAD",
            "address": f"{n} Rue du Test, Quartier Industriel",
            "city": city,
            "region": region,
            "postal_code": postal_code,
            "country": "Maroc",
            "email": f"contact@test-company-{n:03d}.ma",
            "phone": f"+212 6{n:08d}",
            "website": f"https://test-company-{n:03d}.ma",
            "social_links": {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if created_by:
            company["created_by"] = created_by
        companies.append(company)
    return companies


def _main_admin_id(db):
    """Attribute the seeded rows to the platform admin when there is one."""
    admin = db.users.find_one(
        {"role": {"$in": ["main_admin", "admin"]}}, {"_id": 1}
    )
    return admin["_id"] if admin else None


def _seed(db, count, prefix, dry_run):
    created_by = _main_admin_id(db)
    documents = build_companies(count, prefix, created_by)

    existing = {
        c["company_name"]
        for c in db.companies.find(
            {"company_name": {"$regex": f"^{re.escape(prefix)}"}}, {"company_name": 1}
        )
    }
    to_insert = [doc for doc in documents if doc["company_name"] not in existing]

    print(f"Database : {db.name}")
    print(f"Prefix   : {prefix}")
    print(f"Wanted   : {count} companies, {len(existing)} of that name already exist")
    print(f"To insert: {len(to_insert)}")
    if not to_insert:
        print("Nothing to do.")
        return 0
    print(f"Sample   : {to_insert[0]['company_name']} ({to_insert[0]['code']}, ICE {to_insert[0]['ice']})")
    if dry_run:
        print("Dry run: nothing was written.")
        return 0

    db.companies.insert_many(to_insert, ordered=True)
    print(f"Created {len(to_insert)} companies.")
    return len(to_insert)


def _delete(db, prefix, dry_run):
    pattern = re.compile(f"^{re.escape(prefix)}")
    companies = list(db.companies.find({"company_name": pattern}, {"company_name": 1}))
    print(f"Database : {db.name}")
    print(f"Matching companies: {len(companies)}")
    if not companies:
        return 0
    if dry_run:
        for company in companies[:5]:
            print(f"  would remove {company['company_name']}")
        print("Dry run: nothing was deleted.")
        return 0

    company_ids = [company["_id"] for company in companies]
    # Every tenant collection, discovered at run time so no collection is missed.
    for name in db.list_collection_names():
        if name == "companies" or name.startswith("system."):
            continue
        db[name].delete_many({"company_id": {"$in": company_ids}})
    db.companies.delete_many({"_id": {"$in": company_ids}})
    print(f"Deleted {len(company_ids)} companies and their data.")
    return len(company_ids)


def main():
    parser = argparse.ArgumentParser(description="Create or remove Document Manager test companies")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="How many companies (default: %(default)s)")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="Company name prefix (default: %(default)s)")
    parser.add_argument("--delete", action="store_true", help="Remove companies whose name starts with the prefix")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--yes", action="store_true", help="Apply the change")
    args = parser.parse_args()

    if args.count < 1:
        print("ERROR: --count must be at least 1.")
        return 1
    if not args.prefix.strip():
        print("ERROR: --prefix cannot be empty.")
        return 1
    if not (args.dry_run or args.yes):
        print("Nothing written. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    db = get_db()
    if args.delete:
        _delete(db, args.prefix, args.dry_run)
    else:
        _seed(db, args.count, args.prefix, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
