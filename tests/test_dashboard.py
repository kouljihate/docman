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


def test_dashboard_opens_with_the_companies_affairs_card(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    client.set_cookie("access_token", make_token(admin))

    body = client.get("/dashboard").get_data(as_text=True)

    assert 'id="totalAffairs"' in body
    assert "Companies Affairs" in body
    assert body.index('id="totalAffairs"') < body.index('id="totalServices"')
