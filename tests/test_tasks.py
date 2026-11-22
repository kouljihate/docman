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
