#!/usr/bin/env python3
"""Generate dummy Moroccan customers in bulk.

Two modes, both producing the same records as ``POST /api/customers/bulk``:

* ``--via api``   signs in as a local admin and posts the batch to
                  ``/api/customers/bulk`` (fields: username, email,
                  full_name, password, phone, cin).
* ``--via mongo`` writes the documents the bulk endpoint would write, for
                  when no local-admin password is at hand. It stamps the same
                  ``company_id``, ``created_by`` and ``local_admin_id``, so the
                  new customers belong to the company's local admin.

Examples
--------
    python test/generate_customers.py --dry-run
    python test/generate_customers.py --via mongo --count 100
    python test/generate_customers.py --via api --username masd --password '...'

Run it from the repository root (it reads ``.env`` for ``MONGO_URI`` in mongo
mode); inside the stack use ``docker compose exec -T app python test/...``.
"""
import argparse
import os
import random
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

FIRST_NAMES_MALE = [
    "Mohammed", "Ahmed", "Youssef", "Hamza", "Omar", "Mehdi", "Anas", "Ayoub",
    "Ismail", "Reda", "Khalid", "Said", "Rachid", "Abdelilah", "Ilyas", "Zakaria",
    "Badr", "Amine", "Achraf", "Soufiane", "Tarik", "Nabil", "Mounir", "Hicham",
    "Mustapha", "Adil", "Karim", "Yassine", "Othmane", "Walid",
]
FIRST_NAMES_FEMALE = [
    "Fatima Zahra", "Salma", "Imane", "Sara", "Nadia", "Khadija", "Amina", "Hajar",
    "Meryem", "Ghita", "Nisrine", "Sanae", "Asmae", "Loubna", "Hind", "Ilham",
    "Zineb", "Soukaina", "Basma", "Chaimae", "Dounia", "Kenza", "Wissal",
    "Yasmine", "Amal", "Nawal", "Rania", "Siham", "Lamia",
]
LAST_NAMES = [
    "Alaoui", "Bennani", "El Amrani", "Benjelloun", "Tazi", "Fassi", "Berrada",
    "Chraibi", "El Idrissi", "Ouazzani", "Lahlou", "Benkirane", "El Fassi",
    "Bouazza", "Naciri", "Sekkat", "Ziani", "Haddad", "Saidi", "Mansouri",
    "El Khattabi", "Boukhari", "Rahmani", "Belkacem", "Ait Taleb", "Chakiri",
    "El Ghazi", "Moutaouakil", "Benslimane", "Zeroual",
]
# (city, region, postal code)
CITIES = [
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
    ("Safi", "Marrakech-Safi", "46000"),
    ("El Jadida", "Casablanca-Settat", "24000"),
]
PHONE_PREFIXES = ["060", "061", "062", "063", "065", "066", "067", "068", "070", "076"]
CIN_PREFIXES = ["A", "AB", "AD", "AE", "B", "BE", "BH", "BJ", "BK", "C", "CD", "D"]


def slug(text):
    """'Fatima Zahra' -> 'fatimazahra' (ASCII letters only)."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def build_customers(count, password, taken):
    """Return ``count`` customer records shaped like the bulk endpoint payload."""
    customers = []
    for _ in range(count):
        first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        base = f"{slug(first)}.{slug(last)}"
        username, suffix = base, 1
        while username in taken:
            suffix += 1
            username = f"{base}{suffix}"
        taken.add(username)

        city, region, _postal_code = random.choice(CITIES)
        phone = random.choice(PHONE_PREFIXES) + "".join(
            str(random.randint(0, 9)) for _ in range(6)
        )
        cin = random.choice(CIN_PREFIXES) + "".join(
            str(random.randint(0, 9)) for _ in range(6)
        )
        customers.append({
            "username": username,
            "email": f"{username}@example.ma",
            "full_name": full_name,
            "password": password,
            "phone": phone,
            "cin": cin,
            "city": city,
            "region": region,
        })
    return customers


def report(customers):
    print(f"\n{len(customers)} records, e.g.:")
    for record in customers[:5]:
        print("  " + ", ".join([
            record["full_name"], record["username"], record["email"],
            record["phone"], record["cin"], record["city"],
        ]))


def seed_via_api(args, customers):
    import requests

    session = requests.Session()
    login = session.post(
        f"{args.base_url}/api/auth/login",
        json={"username": args.username, "password": args.password},
        timeout=20,
    )
    if login.status_code != 200:
        sys.exit(f"Login failed ({login.status_code}): {login.text[:300]}")

    created = skipped = 0
    errors = []
    for start in range(0, len(customers), 200):
        batch = customers[start:start + 200]
        payload = [
            {key: item[key] for key in
             ("username", "email", "full_name", "password", "phone", "cin")}
            for item in batch
        ]
        res = session.post(f"{args.base_url}/api/customers/bulk", json=payload, timeout=120)
        if res.status_code != 201:
            sys.exit(f"Bulk insert failed ({res.status_code}): {res.text[:300]}")
        result = res.json()
        created += result.get("created", 0)
        skipped += len(result.get("skipped", []))
        errors.extend(result.get("errors", []))
        print(f"batch {start // 200 + 1}: created={result.get('created', 0)} "
              f"skipped={len(result.get('skipped', []))} errors={len(result.get('errors', []))}")

    for item in errors[:10]:
        print("  error:", item)
    print(f"\nDone: {created} created, {skipped} skipped, {len(errors)} errors.")


def seed_via_mongo(args, customers):
    from bcrypt import gensalt, hashpw
    from bson import ObjectId
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv(os.path.join(ROOT, ".env"))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI is not set (expected in .env or the environment).")
    db = MongoClient(uri, serverSelectionTimeoutMS=10000)[
        uri.rsplit("/", 1)[-1].split("?")[0]
    ]

    company = None
    if args.company:
        company = db.companies.find_one({
            "$or": [
                {"company_name": args.company},
                {"code": args.company},
                {"_id": _maybe_oid(args.company)},
            ]
        })
    else:
        company = db.companies.find_one({"is_active": True}) or db.companies.find_one()
    if not company:
        sys.exit("No company found; create one first or pass --company.")
    company_id = company["_id"]

    admin = db.users.find_one(
        {"company_id": company_id, "role": "local_admin", "is_active": True},
        sort=[("created_at", 1)],
    )
    if not admin:
        sys.exit(f"No active local admin in company '{company.get('company_name')}'.")

    hashed = hashpw(args.customer_password.encode("utf-8"), gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc)

    created = skipped = 0
    for item in customers:
        if db.users.find_one({"$or": [
            {"username": item["username"]},
            {"email": item["email"]},
            {"cin": item["cin"]},
        ]}):
            skipped += 1
            continue
        db.users.insert_one({
            "username": item["username"],
            "email": item["email"],
            "password": hashed,
            "role": "customer",
            "full_name": item["full_name"],
            "phone": item["phone"],
            "cin": item["cin"],
            "is_active": True,
            "company_id": company_id,
            "created_by": admin["_id"],
            "local_admin_id": admin["_id"],
            "created_at": now,
            "updated_at": now,
        })
        created += 1

    print(f"\nCompany: {company.get('company_name')} ({company_id})")
    print(f"Local admin: {admin.get('username')} ({admin['_id']})")
    print(f"Done: {created} created, {skipped} skipped. "
          f"Login password for every new customer: {args.customer_password}")


def _maybe_oid(value):
    from bson import ObjectId

    try:
        return ObjectId(value)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate dummy Moroccan customers.")
    parser.add_argument("--via", choices=["api", "mongo"], default="api")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the generated records without writing anything")
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--username", help="local admin username (api mode)")
    parser.add_argument("--password", help="local admin password (api mode)")
    parser.add_argument("--company", help="company name, code or id (mongo mode)")
    parser.add_argument("--customer-password", default="Customer123!",
                        help="password given to every generated customer")
    args = parser.parse_args()

    if args.via == "api" and not args.dry_run and not (args.username and args.password):
        sys.exit("api mode needs --username and --password (a local admin account).")

    taken = set()
    customers = build_customers(args.count, args.customer_password, taken)

    if args.dry_run:
        report(customers)
        print("\nDry run: nothing was written.")
        return

    if args.via == "api":
        seed_via_api(args, customers)
    else:
        seed_via_mongo(args, customers)


if __name__ == "__main__":
    main()
