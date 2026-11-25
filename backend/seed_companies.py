"""Create demo companies (tenants) in the Document Manager database.

Examples (inside the running stack):

    docker compose exec app python seed_companies.py --dry-run
    docker compose exec app python seed_companies.py --yes
    docker compose exec app python seed_companies.py --count 25 --yes
    docker compose exec app python seed_companies.py --delete --yes

The companies use realistic Moroccan names, legal information and contact
details from the curated list below, and each one gets a local admin
(``local_admin``) with a Moroccan full name, its own username/e-mail and the
default password ``looklook``. Company names that already exist are skipped, so
re-running is safe.

``--delete`` removes the seeded companies and every document carrying their
``company_id``.
"""
import argparse
import base64
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:  # when run as a file
    BASE_DIR = Path(__file__).resolve().parent
except NameError:  # when piped through stdin (python -)
    BASE_DIR = Path.cwd()
sys.path.insert(0, str(BASE_DIR))

from bcrypt import gensalt, hashpw

from app.database import get_db
from app.tenancy import LOCAL_ADMIN

DEFAULT_COUNT = 100
DEFAULT_PASSWORD = "looklook"

COMPANY_NAMES = (
    "Atlas Logistique",
    "Maroc Trans Express",
    "Sahara Cargo Services",
    "Tanger Med Transit",
    "Casa Freight",
    "Nord Distribution",
    "Maghreb Approvisionnement",
    "Delta Import Export",
    "Anfa Trading",
    "Oceanic Shipping Maroc",
    "Bâtir Maroc",
    "Construction Atlas",
    "Sahara BTP",
    "Ciment & Structure",
    "Marrakech Habitat",
    "Fès Bâtiment",
    "Agadir Travaux",
    "Oujda Construction",
    "Chaouia BTP",
    "Rif Construction",
    "Digital Atlas",
    "Webfactory Maroc",
    "Sysinfo Casablanca",
    "Cyber Solutions",
    "Data Bridge Maroc",
    "Techno Maghreb",
    "Softline Maroc",
    "Netika Services",
    "Cloud Maroc",
    "Innovatech Rabat",
    "Cabinet El Amrani",
    "Fiduciaire Al Manar",
    "Conseil & Stratégie",
    "Audit Maroc",
    "Expertise Comptable Tanger",
    "Cabinet Benjelloun",
    "Gestion & Finance",
    "Fiscalia Maroc",
    "Argania Nature",
    "Huilerie du Souss",
    "Olivea Maroc",
    "Dattes du Sud",
    "Agrumes Souss",
    "Sardine Atlantique",
    "Saveurs du Maroc",
    "Conserverie Agadir",
    "Textile Fès",
    "Coton Casa",
    "Atelier Tanger",
    "Confection Kénitra",
    "Anfa Immobilier",
    "Palmeraie Promotion",
    "Résidences Rabat",
    "Immobilier Médina",
    "Groupe Foncier Atlas",
    "Solaire Atlas",
    "Énergie Renouvelable Maroc",
    "Green Power Souss",
    "Éco Watt Maroc",
    "Maroc Métal",
    "Plastique Industrie",
    "Menuiserie Aluminium",
    "Marbrerie Atlas",
    "Acier & Fonderie",
    "Mécanique Générale Tanger",
    "Institut Al Kindi",
    "École Langues Atlas",
    "Centre Formation Nour",
    "Académie Digitale",
    "Supérette Al Baraka",
    "Maison du Thé",
    "Épicerie Fine Casablanca",
    "Librairie Al Andalous",
    "Nettoyage Pro",
    "Sécurité Atlas",
    "Espaces Verts Maroc",
    "Clinique Al Amal",
    "Laboratoire Atlas Médical",
    "Cabinet Dentaire Al Farabi",
    "Pharmacie Al Shifa",
    "Optique Média Maroc",
    "Riad Zitoun Voyages",
    "Sahara Tours",
    "Voyages Al Andalous",
    "Hôtel Riad Yasmine",
    "Agence Anfa Travel",
    "Transport Marrakech Express",
    "Logistica Rabat",
    "Cars Atlas",
    "Livraison Rapide Casa",
    "Atelier Couture Fès",
    "Bijouterie Argent Massif",
    "Poterie Atlas",
    "Tapis Beni Ouarain",
    "Cosmétique Argan Bio",
    "Parapharmacie Nour",
    "Édition Al Manar",
    "Studio Graphique Maroc",
    "Imprimerie Atlas",
    "Publicité Médina",
)

FIRST_NAMES = (
    "Youssef",
    "Fatima Zahra",
    "Mohamed",
    "Salma",
    "Hamza",
    "Imane",
    "Karim",
    "Nour",
    "Mehdi",
    "Amina",
    "Omar",
    "Khadija",
    "Yassine",
    "Sara",
    "Rachid",
    "Leila",
    "Anas",
    "Meryem",
    "Hicham",
    "Zineb",
    "Abdelilah",
    "Soukaina",
    "Khalid",
    "Hajar",
    "Ayoub",
    "Asmae",
    "Mustapha",
    "Chaimae",
    "Reda",
    "Ghita",
    "Bilal",
    "Kaoutar",
    "Said",
    "Ikram",
    "Adil",
    "Farah",
    "Nabil",
    "Wafa",
    "Tariq",
    "Nadia",
    "Younes",
    "Sanaa",
    "Aziz",
    "Loubna",
    "Sofiane",
    "Kenza",
    "Brahim",
    "Amal",
    "Jalil",
    "Rania",
)

LAST_NAMES = (
    "El Amrani",
    "Benjelloun",
    "Alaoui",
    "Bennani",
    "Tazi",
    "Berrada",
    "Idrissi",
    "Chakiri",
    "Fassi",
    "Loukili",
    "Ouazzani",
    "Bouzidi",
    "Naciri",
    "Sekkat",
    "Belkacem",
    "Cherkaoui",
    "El Khattabi",
    "Mansouri",
    "Bouhaddou",
    "Zerouali",
    "Ait Taleb",
    "Benkirane",
    "Skalli",
    "Filali",
    "El Yousfi",
    "Chraibi",
    "Lahlou",
    "Kabbaj",
    "Bennis",
    "Essaid",
    "Ghali",
    "Marzouki",
    "Boughaleb",
    "Naji",
    "Hamdaoui",
    "Rachidi",
    "Belmekki",
    "Ouali",
    "Tahiri",
    "Ziani",
    "Kettani",
    "Daoudi",
    "Slaoui",
    "Moutaouakil",
    "Bourkia",
    "Chaoui",
    "Jebbari",
    "Zniber",
    "Mekouar",
    "Boutaleb",
)

LEGAL_FORMS = (
    "SARL",
    "SARL AU",
    "SA",
    "SAS",
    "SNC",
    "Auto-entrepreneur",
    "Coopérative",
)

CAPITALS = ("100 000 MAD", "250 000 MAD", "500 000 MAD", "1 000 000 MAD")

LOGO_PALETTE = (
    ("#C1440E", "#E8A33D"),
    ("#1B4B8A", "#3C8DBC"),
    ("#0F6E5C", "#46B295"),
    ("#6B2D5B", "#B25E9C"),
    ("#2F4F2F", "#7BA05B"),
    ("#8C2F39", "#D9838B"),
    ("#2B2D42", "#8D99AE"),
    ("#A15C00", "#F2B33D"),
)

LOGO_STOPWORDS = {
    "et",
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "au",
    "aux",
    "el",
    "al",
}

STREETS = (
    "Boulevard Mohammed V",
    "Avenue Hassan II",
    "Rue Ibn Batouta",
    "Boulevard Zerktouni",
    "Rue Al Massira",
    "Avenue des Forces Armées Royales",
    "Rue de la Liberté",
    "Boulevard Allal El Fassi",
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

# A company named after a city is based there; the rest rotate.
CITY_HINTS = (
    ("Casablanca", "Casablanca"),
    ("Casa", "Casablanca"),
    ("Rabat", "Rabat"),
    ("Marrakech", "Marrakech"),
    ("Fès", "Fès"),
    ("Fes", "Fès"),
    ("Tanger", "Tanger"),
    ("Agadir", "Agadir"),
    ("Oujda", "Oujda"),
    ("Kénitra", "Kénitra"),
    ("Kenitra", "Kénitra"),
    ("Souss", "Agadir"),
    ("Tétouan", "Tétouan"),
)


def _ascii(value):
    """Strip accents so names can be used in slugs, usernames and e-mails."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _slug(value):
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in _ascii(value))
    return "-".join(cleaned.split())


def _logo_initials(name):
    """Two meaningful initials, skipping connectors such as "de" or "Al"."""
    words = [
        word
        for word in re.split(r"[\s\-]+", _ascii(name))
        if word.isalpha() and word.lower() not in LOGO_STOPWORDS
    ]
    if not words:
        return _ascii(name)[:2].upper()
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _logo_data_url(name, index):
    """A small, self-contained SVG monogram used as the company logo."""
    primary, accent = LOGO_PALETTE[index % len(LOGO_PALETTE)]
    initials = _logo_initials(name)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" '
        'viewBox="0 0 128 128">'
        f'<rect width="128" height="128" rx="28" fill="{primary}"/>'
        f'<circle cx="104" cy="22" r="42" fill="{accent}" opacity="0.35"/>'
        '<text x="64" y="66" fill="#FFFFFF" font-family="Helvetica,Arial,sans-serif" '
        'font-size="52" font-weight="700" text-anchor="middle" '
        f'dominant-baseline="middle" letter-spacing="1">{initials}</text>'
        '</svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _location(name, index):
    for hint, city in CITY_HINTS:
        if hint in name:
            return next(location for location in LOCATIONS if location[0] == city)
    return LOCATIONS[index % len(LOCATIONS)]


def _admin_name(index):
    """A deterministic Moroccan full name, unique for the curated batch."""
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    cycle = index // len(FIRST_NAMES)
    last = LAST_NAMES[(index + cycle * 13) % len(LAST_NAMES)]
    return first, last


def build_companies(count=DEFAULT_COUNT, created_by=None, now=None):
    """Build ``count`` companies, each with its first local admin.

    Returns a list of ``{"company": <document>, "admin": {username, email,
    full_name}}``; the admin's ``company_id`` is only known once the company is
    inserted, so the caller adds it.
    """
    if count > len(COMPANY_NAMES):
        raise ValueError(f"only {len(COMPANY_NAMES)} company names are curated")
    now = now or datetime.now(timezone.utc)
    tenants = []
    used_usernames = set()
    used_slugs = set()

    for index, name in enumerate(COMPANY_NAMES[:count]):
        slug = _slug(name)
        if slug in used_slugs:
            raise ValueError(f"duplicate company slug: {slug}")
        used_slugs.add(slug)

        city, region, postal_code = _location(name, index)
        first, last = _admin_name(index)
        full_name = f"{first} {last}"
        base_username = f"{_slug(first)[0]}.{_slug(last).replace('-', '')}"
        username = base_username
        suffix = 2
        while username in used_usernames:
            username = f"{base_username}{suffix}"
            suffix += 1
        used_usernames.add(username)

        company = {
            "company_name": name,
            "code": slug.upper(),
            "slogan": "",
            "logo": _logo_data_url(name, index),
            "legal_form": LEGAL_FORMS[index % len(LEGAL_FORMS)],
            # 15 digits, unique per company.
            "ice": f"{150_000_000_000_000 + index + 1}",
            "rc": f"RC {city} {10_000 + index + 1}",
            "tax_id": f"{30_000_000 + index + 1}",
            "patente": f"{6_000_000 + index + 1}",
            "cnss": f"{900_000 + index + 1}",
            "capital": CAPITALS[index % len(CAPITALS)],
            "address": f"{10 + index} {STREETS[index % len(STREETS)]}",
            "city": city,
            "region": region,
            "postal_code": postal_code,
            "country": "Maroc",
            "email": f"contact@{slug}.ma",
            "phone": f"+212 6{index + 1:08d}",
            "website": f"https://{slug}.ma",
            "social_links": {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if created_by:
            company["created_by"] = created_by
        tenants.append(
            {
                "company": company,
                "admin": {
                    "username": username,
                    "full_name": full_name,
                    "email": f"{username}@{slug}.ma",
                },
            }
        )
    return tenants


def _main_admin_id(db):
    """Attribute the seeded rows to the platform admin when there is one."""
    admin = db.users.find_one({"role": {"$in": ["main_admin", "admin"]}}, {"_id": 1})
    return admin["_id"] if admin else None


def _admin_document(admin, company_id, password_hash, created_by, now):
    document = {
        "username": admin["username"],
        "email": admin["email"],
        "password": password_hash,
        "role": LOCAL_ADMIN,
        "full_name": admin["full_name"],
        "phone": None,
        "is_active": True,
        "company_id": company_id,
        "created_at": now,
        "updated_at": now,
    }
    if created_by:
        document["created_by"] = created_by
    return document


def _seed(db, count, dry_run):
    now = datetime.now(timezone.utc)
    created_by = _main_admin_id(db)
    tenants = build_companies(count, created_by, now)

    existing = {
        company["company_name"]
        for company in db.companies.find(
            {"company_name": {"$in": [tenant["company"]["company_name"] for tenant in tenants]}},
            {"company_name": 1},
        )
    }
    pending = [tenant for tenant in tenants if tenant["company"]["company_name"] not in existing]
    taken_users = {
        user.get("username")
        for user in db.users.find(
            {"username": {"$in": [tenant["admin"]["username"] for tenant in tenants]}},
            {"username": 1},
        )
    }

    print(f"Database : {db.name}")
    print(f"Wanted   : {count} companies, {len(existing)} already exist")
    print(f"To insert: {len(pending)} companies with a local admin each")
    if not pending:
        print("Nothing to do.")
        return 0
    sample = pending[0]
    print(f"Sample   : {sample['company']['company_name']} ({sample['company']['city']})")
    print(f"           admin {sample['admin']['full_name']} / {sample['admin']['username']} / {DEFAULT_PASSWORD}")
    if dry_run:
        print("Dry run: nothing was written.")
        return 0

    # Every seeded admin shares the same default password, so one hash is enough.
    password_hash = hashpw(DEFAULT_PASSWORD.encode("utf-8"), gensalt()).decode("utf-8")

    created = 0
    for tenant in pending:
        company_id = db.companies.insert_one(tenant["company"]).inserted_id
        if tenant["admin"]["username"] in taken_users:
            continue
        db.users.insert_one(
            _admin_document(tenant["admin"], company_id, password_hash, created_by, now)
        )
        taken_users.add(tenant["admin"]["username"])
        created += 1
    print(f"Created {len(pending)} companies and {created} local admins.")
    return len(pending)


def _delete(db, count, dry_run):
    names = list(COMPANY_NAMES[:count])
    companies = list(db.companies.find({"company_name": {"$in": names}}, {"company_name": 1}))
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
    parser = argparse.ArgumentParser(description="Create or remove Document Manager demo companies")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="How many companies (default: %(default)s)")
    parser.add_argument("--delete", action="store_true", help="Remove the seeded companies and their data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--yes", action="store_true", help="Apply the change")
    args = parser.parse_args()

    if not 1 <= args.count <= len(COMPANY_NAMES):
        print(f"ERROR: --count must be between 1 and {len(COMPANY_NAMES)}.")
        return 1
    if not (args.dry_run or args.yes):
        print("Nothing written. Re-run with --dry-run to preview or --yes to apply.")
        return 0

    db = get_db()
    if args.delete:
        _delete(db, args.count, args.dry_run)
    else:
        _seed(db, args.count, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
