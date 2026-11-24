def _add_affair(db, company_id):
    db.affairs.insert_one({"company_id": company_id, "reference": "A 260101-0001", "title": "Affair"})


def test_stats_count_only_the_company_affairs(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    other = make_company("Other", "other")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _add_affair(db, company["_id"])
    _add_affair(db, company["_id"])
    _add_affair(db, other["_id"])
    client.set_cookie("access_token", make_token(admin))

    data = client.get("/api/dashboard/stats").get_json()

    assert data["affairs_count"] == 2


def test_main_admin_dashboard_separates_companies_from_affairs(
    client, make_token, make_user, make_company
):
    make_company("Acme", "acme")
    root = make_user("main_admin", "root")
    client.set_cookie("access_token", make_token(root))

    body = client.get("/dashboard").get_data(as_text=True)

    # Companies and affairs are two counters, each linking to its own page.
    assert 'id="totalCompanies"' in body
    assert 'id="totalAffairs"' in body
    assert "Companies Affairs" not in body
    assert body.index('id="totalCompanies"') < body.index('id="totalAffairs"')
    assert body.index('id="totalAffairs"') < body.index('id="totalServices"')
    assert 'href="/companies"' in body
    assert 'href="/affairs"' in body


def test_local_admin_dashboard_shows_no_companies_counter(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    client.set_cookie("access_token", make_token(admin))

    body = client.get("/dashboard").get_data(as_text=True)

    assert 'id="totalAffairs"' in body
    assert 'id="totalCompanies"' not in body
    assert body.index('id="totalAffairs"') < body.index('id="totalServices"')
