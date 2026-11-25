import base64
from xml.etree import ElementTree

from seed_companies import COMPANY_NAMES, DEFAULT_PASSWORD, build_companies


def test_build_companies_uses_unique_realistic_names():
    tenants = build_companies(100)

    names = [tenant["company"]["company_name"] for tenant in tenants]
    assert names == list(COMPANY_NAMES[:100])
    assert len(set(names)) == 100
    assert not any("Test Company" in name or name.endswith((" 001", " 100")) for name in names)

    slugs = [tenant["company"]["code"] for tenant in tenants]
    websites = [tenant["company"]["website"] for tenant in tenants]
    assert len(set(slugs)) == 100
    assert len(set(websites)) == 100

    ices = [tenant["company"]["ice"] for tenant in tenants]
    assert len(set(ices)) == 100
    assert all(len(ice) == 15 and ice.isdigit() for ice in ices)
    assert all(tenant["company"]["city"] for tenant in tenants)


def test_build_companies_creates_a_unique_local_admin_each():
    tenants = build_companies(100)

    usernames = [tenant["admin"]["username"] for tenant in tenants]
    emails = [tenant["admin"]["email"] for tenant in tenants]
    assert len(set(usernames)) == 100
    assert len(set(emails)) == 100
    # Compound first names such as "Fatima Zahra" are allowed.
    assert all(len(tenant["admin"]["full_name"].split()) >= 2 for tenant in tenants)
    assert all(tenant["admin"]["username"] == tenant["admin"]["username"].lower() for tenant in tenants)
    for tenant in tenants:
        assert tenant["admin"]["email"].startswith(tenant["admin"]["username"] + "@")
        assert tenant["admin"]["email"].endswith(".ma")
    assert DEFAULT_PASSWORD == "looklook"


def test_build_companies_have_a_valid_branded_logo():
    tenants = build_companies(100)

    logos = [tenant["company"]["logo"] for tenant in tenants]
    assert all(logo.startswith("data:image/svg+xml;base64,") for logo in logos)
    assert len({logo for logo in logos}) > 50
    assert all(len(logo) < 900_000 for logo in logos)  # MAX_LOGO_LENGTH
    for logo, tenant in zip(logos, tenants):
        svg = base64.b64decode(logo.split(",", 1)[1]).decode("utf-8")
        root = ElementTree.fromstring(svg)  # well-formed SVG
        text = root.find("{http://www.w3.org/2000/svg}text")
        assert text is not None and text.text.strip()
        assert len(text.text.strip()) == 2


def test_build_companies_matches_named_cities():
    tenants = {t["company"]["company_name"]: t["company"] for t in build_companies(100)}

    assert tenants["Fès Bâtiment"]["city"] == "Fès"
    assert tenants["Marrakech Habitat"]["city"] == "Marrakech"
    assert tenants["Transport Marrakech Express"]["city"] == "Marrakech"
    assert tenants["Coton Casa"]["city"] == "Casablanca"
