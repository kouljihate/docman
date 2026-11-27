from datetime import datetime, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _task(company_id, created_by, **extra):
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "title": "Analyse fiscale",
        "description": "Analyser la situation fiscale de l'entreprise.",
        "status": "pending",
        "company_id": company_id,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    return doc


def test_task_list_returns_service_id(client, db, make_token, make_user, make_company):
    """The services page groups tasks by service_id, so the API must expose it."""
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    service_id = ObjectId()
    db.services.insert_one(
        {
            "_id": service_id,
            "name": "Conseil fiscal",
            "description": "",
            "price": None,
            "is_active": True,
            "task_ids": [],
            "company_id": company["_id"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    db.tasks.insert_one(_task(company["_id"], admin["_id"], service_id=service_id))

    _login(client, make_token, admin)
    response = client.get("/api/tasks/")

    assert response.status_code == 200
    tasks = response.get_json()
    assert len(tasks) == 1
    assert tasks[0]["service_id"] == str(service_id)
    assert tasks[0]["title"] == "Analyse fiscale"


def test_employee_created_task_notifies_the_local_admin(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    employee = make_user("local_employee", "acme-employee", company["_id"])
    _login(client, make_token, employee)

    response = client.post(
        "/api/tasks/", json={"title": "Classer les dossiers", "description": "Archiver 2025"}
    )

    assert response.status_code == 201
    task_id = ObjectId(response.get_json()["_id"])
    notification = db.notifications.find_one(
        {"user_id": admin["_id"], "type": "task_validation"}
    )
    assert notification is not None
    assert notification["task_id"] == task_id
    assert notification["company_id"] == company["_id"]
    assert notification["read"] is False
    assert "Classer les dossiers" in notification["message"]


def test_admin_created_task_sends_no_validation_notification(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    make_user("local_employee", "acme-employee", company["_id"])
    _login(client, make_token, admin)

    assert client.post("/api/tasks/", json={"title": "Relire le contrat"}).status_code == 201
    assert db.notifications.count_documents({"type": "task_validation"}) == 0


def test_employee_tasks_page_shows_two_columns_and_the_new_task_button(
    client, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    _login(client, make_token, employee)

    body = client.get("/tasks").get_data(as_text=True)

    # Only the two reading columns survive; the action buttons are gone.
    assert "Task Title</th>" in body
    assert "Description</th>" in body
    assert "Actions</th>" not in body
    assert 'colspan="2"' in body
    # The New task button is declared for the table toolbar, before Export.
    assert 'id="newTaskBtn"' in body
    assert "data-table-toolbar" in body


def test_local_admin_tasks_page_keeps_the_actions_column(
    client, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    body = client.get("/tasks").get_data(as_text=True)

    assert "Actions</th>" in body
    assert 'id="newTaskBtn"' in body
    assert "data-table-toolbar" in body
