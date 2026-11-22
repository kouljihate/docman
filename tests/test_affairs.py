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
