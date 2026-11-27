from datetime import datetime, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _company(db, name, code):
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "company_name": name,
        "code": code,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.companies.insert_one(doc)
    return doc


def test_company_list_is_paginated(client, db, make_token, make_user):
    root = make_user("main_admin", "root")
    for index in range(30):
        _company(db, f"Company {index:02d}", f"c{index:02d}")
    _login(client, make_token, root)

    first = client.get("/api/companies/").get_json()
    assert (first["page"], first["per_page"], first["total"], first["pages"]) == (1, 25, 30, 2)
    assert len(first["items"]) == 25
    assert first["items"][0]["company_name"] == "Company 00"
    assert first["items"][-1]["company_name"] == "Company 24"

    second = client.get("/api/companies/?page=2").get_json()
    assert [c["company_name"] for c in second["items"]][0] == "Company 25"
    assert len(second["items"]) == 5

    # A page past the end falls back to the last one instead of an empty table.
    assert client.get("/api/companies/?page=9").get_json()["page"] == 2

    # Search still narrows the total and the page size is capped.
    found = client.get("/api/companies/?q=Company 1").get_json()
    assert found["total"] == 10
    assert client.get("/api/companies/?per_page=9999").get_json()["per_page"] == 200


def test_company_counts_come_from_one_aggregation(client, db, make_token, make_user):
    root = make_user("main_admin", "root")
    acme = _company(db, "Acme", "acme")
    other = _company(db, "Other", "other")

    for role in ("local_admin", "local_employee", "customer", "customer"):
        make_user(role, f"acme-{role}-{ObjectId()}", acme["_id"])
    make_user("customer", "other-customer", other["_id"])

    for _ in range(2):
        db.affairs.insert_one({"company_id": acme["_id"]})
    db.affairs.insert_one({"company_id": other["_id"]})
    db.documents.insert_one({"company_id": acme["_id"]})
    db.tasks.insert_many([{"company_id": acme["_id"]}, {"company_id": acme["_id"]}])

    _login(client, make_token, root)
    items = {c["company_name"]: c for c in client.get("/api/companies/").get_json()["items"]}

    acme_row = items["Acme"]
    assert (acme_row["admins_count"], acme_row["employees_count"], acme_row["customers_count"]) == (1, 1, 2)
    assert (acme_row["affairs_count"], acme_row["documents_count"], acme_row["tasks_count"]) == (2, 1, 2)

    other_row = items["Other"]
    assert (other_row["admins_count"], other_row["customers_count"], other_row["affairs_count"]) == (0, 1, 1)
    assert (other_row["documents_count"], other_row["tasks_count"]) == (0, 0)


def test_company_detail_exposes_its_local_admin(client, db, make_token, make_user):
    root = make_user("main_admin", "root")
    company = _company(db, "Acme", "acme")
    make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, root)

    detail = client.get(f"/api/companies/{company['_id']}").get_json()
    assert detail["admin"]["username"] == "acme-admin"
    assert detail["admins"][0]["username"] == "acme-admin"


def test_company_edit_updates_the_local_admin(client, db, make_token, make_user):
    from bcrypt import checkpw

    root = make_user("main_admin", "root")
    company = _company(db, "Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, root)

    response = client.put(
        f"/api/companies/{company['_id']}",
        json={
            "admin_full_name": "New Name",
            "admin_username": "acme-new",
            "admin_email": "new-admin@example.com",
            "admin_password": "secret123",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["admin"]["username"] == "acme-new"

    stored = db.users.find_one({"_id": admin["_id"]})
    assert stored["username"] == "acme-new"
    assert stored["full_name"] == "New Name"
    assert stored["email"] == "new-admin@example.com"
    assert checkpw(b"secret123", stored["password"].encode("utf-8"))


def test_company_edit_keeps_the_password_when_it_is_not_sent(client, db, make_token, make_user):
    root = make_user("main_admin", "root")
    company = _company(db, "Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    before = db.users.find_one({"_id": admin["_id"]})["password"]
    _login(client, make_token, root)

    response = client.put(f"/api/companies/{company['_id']}", json={"admin_full_name": "Renamed"})

    assert response.status_code == 200
    assert db.users.find_one({"_id": admin["_id"]})["password"] == before


def test_company_edit_rejects_an_admin_username_already_taken(client, db, make_token, make_user):
    root = make_user("main_admin", "root")
    company = _company(db, "Acme", "acme")
    make_user("local_admin", "acme-admin", company["_id"])
    make_user("local_admin", "other-admin", None)
    _login(client, make_token, root)

    response = client.put(f"/api/companies/{company['_id']}", json={"admin_username": "other-admin"})

    assert response.status_code == 409
    assert db.users.find_one({"username": "acme-admin"}) is not None
