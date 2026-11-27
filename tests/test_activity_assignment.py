from datetime import datetime, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _setup(make_company, make_user, db):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    employee = make_user("local_employee", "acme-emp", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    return company, admin, employee, customer


def _service(db, company_id, name="Conseil fiscal"):
    now = datetime.now(timezone.utc)
    service_id = ObjectId()
    db.services.insert_one(
        {
            "_id": service_id,
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
    return service_id


def _create_affair(client, name, customer, **extra):
    payload = {
        "name": name,
        "affair_type": "individual",
        "customer_id": str(customer["_id"]),
        "generate_activities": True,
    }
    payload.update(extra)
    return client.post("/api/affairs/", json=payload)


def test_affair_without_service_still_gets_a_pending_activity(
    client, db, make_token, make_user, make_company
):
    company, admin, _employee, customer = _setup(make_company, make_user, db)
    _login(client, make_token, admin)

    response = _create_affair(client, "Dossier sans service", customer)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["activity_count"] == 1

    activity = db.activities.find_one({"company_id": company["_id"]})
    assert activity["title"] == "Dossier sans service"
    assert activity["status"] == "pending"
    assert activity["assigned_to"] is None
    assert activity["service_id"] is None


def test_affair_with_services_and_no_assignee_stays_pending(
    client, db, make_token, make_user, make_company
):
    company, admin, _employee, customer = _setup(make_company, make_user, db)
    service_id = _service(db, company["_id"])
    _login(client, make_token, admin)

    response = _create_affair(client, "Dossier fiscal", customer, service_ids=[str(service_id)])

    assert response.status_code == 201, response.get_json()
    activity = db.activities.find_one({"company_id": company["_id"]})
    assert activity["status"] == "pending"
    assert activity["assigned_to"] is None
    assert activity["service_id"] == service_id


def test_local_admin_assignment_sets_the_assigned_status(
    client, db, make_token, make_user, make_company
):
    company, admin, employee, customer = _setup(make_company, make_user, db)
    _login(client, make_token, admin)
    _create_affair(client, "Dossier à affecter", customer)
    activity = db.activities.find_one({"company_id": company["_id"]})

    response = client.put(
        f"/api/activities/{activity['_id']}/assign",
        json={"assigned_to": str(employee["_id"])},
    )

    assert response.status_code == 200, response.get_json()
    stored = db.activities.find_one({"_id": activity["_id"]})
    assert stored["status"] == "assigned"
    assert stored["assigned_to"] == employee["_id"]
    assert db.notifications.find_one({"user_id": employee["_id"], "type": "activity_assigned"})


def test_assigned_activity_appears_in_the_employee_list_and_can_be_started(
    client, db, make_token, make_user, make_company
):
    company, admin, employee, customer = _setup(make_company, make_user, db)
    _login(client, make_token, admin)
    _create_affair(client, "Dossier suivi", customer)
    activity = db.activities.find_one({"company_id": company["_id"]})
    client.put(
        f"/api/activities/{activity['_id']}/assign",
        json={"assigned_to": str(employee["_id"])},
    )

    _login(client, make_token, employee)
    mine = client.get("/api/activities/").get_json()
    assert [a["_id"] for a in mine] == [str(activity["_id"])]
    assert mine[0]["status"] == "assigned"

    started = client.put(
        f"/api/activities/{activity['_id']}/status", json={"status": "in_progress"}
    )
    assert started.status_code == 200, started.get_json()
    assert db.activities.find_one({"_id": activity["_id"]})["status"] == "in_progress"

    completed = client.put(
        f"/api/activities/{activity['_id']}/status", json={"status": "completed"}
    )
    assert completed.status_code == 200, completed.get_json()
    assert db.activities.find_one({"_id": activity["_id"]})["status"] == "completed"


def test_employee_cannot_complete_before_starting(client, db, make_token, make_user, make_company):
    company, admin, employee, customer = _setup(make_company, make_user, db)
    _login(client, make_token, admin)
    _create_affair(client, "Dossier à démarrer", customer)
    activity = db.activities.find_one({"company_id": company["_id"]})
    client.put(
        f"/api/activities/{activity['_id']}/assign",
        json={"assigned_to": str(employee["_id"])},
    )

    _login(client, make_token, employee)
    refused = client.put(
        f"/api/activities/{activity['_id']}/status", json={"status": "completed"}
    )

    assert refused.status_code == 400
    assert db.activities.find_one({"_id": activity["_id"]})["status"] == "assigned"


def test_assigning_the_affair_hands_over_its_waiting_activities(
    client, db, make_token, make_user, make_company
):
    company, admin, employee, customer = _setup(make_company, make_user, db)
    _login(client, make_token, admin)
    created = _create_affair(client, "Dossier global", customer).get_json()

    response = client.put(
        f"/api/affairs/{created['_id']}", json={"assigned_to": str(employee["_id"])}
    )

    assert response.status_code == 200, response.get_json()
    activity = db.activities.find_one({"affair_id": ObjectId(created["_id"])})
    assert activity["status"] == "assigned"
    assert activity["assigned_to"] == employee["_id"]
