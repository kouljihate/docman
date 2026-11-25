import re
from datetime import datetime, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _seed_services(db, company_id, names):
    now = datetime.now(timezone.utc)
    service_ids = []
    for name in names:
        sid = ObjectId()
        db.services.insert_one(
            {
                "_id": sid,
                "name": name,
                "description": "",
                "price": None,
                "is_active": True,
                "task_ids": [],
                "company_id": company_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        service_ids.append(str(sid))
    return service_ids


def test_affair_generates_one_activity_per_service(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    employee = make_user("local_employee", "acme-emp", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    service_ids = _seed_services(db, company["_id"], ["Conseil fiscal", "Étude"])

    _login(client, make_token, admin)
    response = client.post(
        "/api/affairs/",
        json={
            "name": "Dossier SARL Atlas",
            "affair_type": "enterprise",
            "customer_id": str(customer["_id"]),
            "service_ids": service_ids,
            "assigned_to": str(employee["_id"]),
            "generate_activities": True,
        },
    )

    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    assert payload["assigned_to"] == str(employee["_id"])
    assert re.fullmatch(r"A\d{6}-\d{4}", payload["reference"]), payload["reference"]
    assert sorted(payload["service_names"]) == sorted(["Conseil fiscal", "Étude"])
    assert payload["activity_count"] == 2

    activities = list(db.activities.find({"affair_id": ObjectId(payload["_id"])}))
    assert len(activities) == 2
    assert {a["assigned_to"] for a in activities} == {employee["_id"]}
    assert {a["customer_id"] for a in activities} == {customer["_id"]}
    assert db.notifications.count_documents({"user_id": employee["_id"]}) == 2

    # Re-running generation is idempotent: no duplicates.
    again = client.post(f"/api/affairs/{payload['_id']}/activities")
    assert again.status_code == 200
    assert again.get_json()["created"] == 0
    assert db.activities.count_documents({"affair_id": ObjectId(payload["_id"])}) == 2


def test_affair_references_are_unique_per_company(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    _login(client, make_token, admin)

    references = []
    for name in ("Dossier A", "Dossier B"):
        response = client.post(
            "/api/affairs/",
            json={
                "name": name,
                "customer_id": str(customer["_id"]),
                "service_ids": [],
                "generate_activities": False,
            },
        )
        assert response.status_code == 201, response.get_json()
        references.append(response.get_json()["reference"])

    assert references[0] != references[1]
    assert all(re.fullmatch(r"A\d{6}-\d{4}", ref) for ref in references)
    listed = client.get("/api/affairs/").get_json()
    assert {a["reference"] for a in listed} == set(references)


def _seed_affair(db, company_id, customer_id, name, reference):
    now = datetime.now(timezone.utc)
    db.affairs.insert_one(
        {
            "name": name,
            "affair_type": "individual",
            "reference": reference,
            "company_id": company_id,
            "customer_id": customer_id,
            "service_ids": [],
            "assigned_to": None,
            "created_at": now,
            "updated_at": now,
        }
    )


def test_platform_admin_lists_affairs_per_company(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    other = make_company("Other", "other")
    acme_customer = make_user("customer", "acme-customer", acme["_id"])
    other_customer = make_user("customer", "other-customer", other["_id"])
    root = make_user("main_admin", "root")
    _seed_affair(db, acme["_id"], acme_customer["_id"], "Dossier A", "A260101-0001")
    _seed_affair(db, acme["_id"], acme_customer["_id"], "Dossier B", "A260101-0002")
    _seed_affair(db, other["_id"], other_customer["_id"], "Dossier C", "A260101-0003")
    _login(client, make_token, root)

    listing = client.get("/api/affairs/").get_json()
    assert {a["company_name"] for a in listing} == {"Acme", "Other"}
    assert all(a["company_id"] for a in listing)

    filtered = client.get(f"/api/affairs/?company_id={acme['_id']}").get_json()
    assert {a["name"] for a in filtered} == {"Dossier A", "Dossier B"}

    companies = client.get("/api/companies/").get_json()["items"]
    counts = {c["company_name"]: c["affairs_count"] for c in companies}
    assert counts == {"Acme": 2, "Other": 1}

    page = client.get(f"/affairs?company={acme['_id']}").get_data(as_text=True)
    assert 'id="affairsTableBody"' in page
    assert f"const companyFilter = \"{acme['_id']}\"" in page


def test_local_admin_cannot_filter_another_company(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    other = make_company("Other", "other")
    acme_customer = make_user("customer", "acme-customer", acme["_id"])
    other_customer = make_user("customer", "other-customer", other["_id"])
    admin = make_user("local_admin", "acme-admin", acme["_id"])
    _seed_affair(db, acme["_id"], acme_customer["_id"], "Dossier A", "A260101-0001")
    _seed_affair(db, other["_id"], other_customer["_id"], "Dossier C", "A260101-0002")
    _login(client, make_token, admin)

    listing = client.get(f"/api/affairs/?company_id={other['_id']}").get_json()
    assert [a["name"] for a in listing] == ["Dossier A"]


def test_affairs_page_renders(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    response = client.get("/affairs")
    assert response.status_code == 200
    page = response.data.decode("utf-8")
    assert 'id="affairServices"' in page
    assert "/users/assignees" in page
    assert 'id="affairReference"' in page


def test_affair_can_be_assigned_to_local_manager(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    manager = make_user("local_admin", "acme-mgr", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    service_ids = _seed_services(db, company["_id"], ["Domiciliation"])

    _login(client, make_token, manager)
    response = client.post(
        "/api/affairs/",
        json={
            "name": "Dossier Domiciliation",
            "customer_id": str(customer["_id"]),
            "service_ids": service_ids,
            "assigned_to": str(manager["_id"]),
        },
    )

    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    assert payload["activity_count"] == 1
    activity = db.activities.find_one({"affair_id": ObjectId(payload["_id"])})
    assert activity["assigned_to"] == manager["_id"]
