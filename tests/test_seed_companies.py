from seed_companies import build_companies


def test_build_companies_makes_unique_valid_tenants():
    companies = build_companies(100)

    assert len(companies) == 100
    assert len({c["company_name"] for c in companies}) == 100
    assert companies[0]["company_name"] == "Test Company 001"
    assert companies[-1]["company_name"] == "Test Company 100"
    assert len({c["ice"] for c in companies}) == 100
    assert all(len(c["ice"]) == 15 and c["ice"].isdigit() for c in companies)
    assert all(c["is_active"] is True for c in companies)
    assert all(c["email"] and c["code"] for c in companies)


def test_build_companies_accepts_prefix_and_count():
    companies = build_companies(3, prefix="Demo")

    assert [c["company_name"] for c in companies] == ["Demo 001", "Demo 002", "Demo 003"]
