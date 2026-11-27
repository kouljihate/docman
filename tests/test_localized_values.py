from datetime import datetime, timezone

from bson import ObjectId

from app.data.service_catalog import LANGUAGES, SERVICES, service_for_name, task_for


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _service(company_id, name):
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "name": name["fr"],
        "name_i18n": name,
        "description": None,
        "price": None,
        "is_active": True,
        "task_ids": [],
        "company_id": company_id,
        "created_at": now,
        "updated_at": now,
    }


def _task(company_id, created_by, title, text):
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "title": title["fr"],
        "title_i18n": title,
        "description": text["fr"],
        "description_i18n": text,
        "status": "pending",
        "company_id": company_id,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def test_catalogue_covers_every_service_and_task_in_three_languages():
    assert len(SERVICES) == 6
    for service in SERVICES:
        assert set(service["name"]) == set(LANGUAGES)
        assert len(service["tasks"]) == 6
        for task in service["tasks"]:
            assert set(task["title"]) == set(LANGUAGES)
            assert set(task["text"]) == set(LANGUAGES)
            for lang in LANGUAGES:
                assert len(task["title"][lang]) <= 48
                assert len(task["text"][lang]) > len(task["title"][lang])


def test_catalogue_matches_rows_in_any_language():
    assert service_for_name("Conseil fiscal") is SERVICES[1]
    assert service_for_name("tax advisory") is SERVICES[1]
    assert service_for_name("الاستشارة الجبائية") is SERVICES[1]

    task = task_for("Analyser la situation fiscale de l'entreprise.")
    assert task is not None
    assert task["title"]["en"] == "Analyse the tax position"
    assert task_for("Analyse the tax position") is task


def test_task_values_follow_the_selected_language(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    task = task_for("Analyser la situation fiscale de l'entreprise.")
    db.tasks.insert_one(_task(company["_id"], admin["_id"], task["title"], task["text"]))

    _login(client, make_token, admin)

    english = client.get("/api/tasks/").get_json()[0]
    assert english["title"] == "Analyse the tax position"
    assert english["description"].startswith("Analyse the company's tax position")

    client.set_cookie("lang", "fr")
    french = client.get("/api/tasks/").get_json()[0]
    assert french["title"] == "Analyser la situation fiscale de l'entreprise"

    client.set_cookie("lang", "ar")
    arabic = client.get("/api/tasks/").get_json()[0]
    assert arabic["title"] == "تحليل الوضع الجبائي"
    assert arabic["description"].startswith("تحليل الوضع الجبائي للمؤسسة")


def test_service_names_follow_the_selected_language(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    db.services.insert_one(_service(company["_id"], SERVICES[5]["name"]))

    _login(client, make_token, admin)
    client.set_cookie("lang", "en")

    service = client.get("/api/services/").get_json()[0]
    assert service["name"] == "Debt collection"
