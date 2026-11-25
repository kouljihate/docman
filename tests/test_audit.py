from datetime import datetime, timezone


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _log(db, company_id, entity_type="task"):
    db.audit_logs.insert_one(
        {
            "action": "create",
            "entity_type": entity_type,
            "entity_id": "abc",
            "performed_by": "def",
            "changes": {},
            "description": "created",
            "created_at": datetime.now(timezone.utc),
            "company_id": company_id,
        }
    )


def test_clean_removes_audit_logs(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    _log(db, acme["_id"])
    _log(db, None, "auth")
    root = make_user("main_admin", "root")
    _login(client, make_token, root)

    resp = client.delete("/api/audit/logs")

    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == 2
    assert db.audit_logs.count_documents({}) == 0


def test_clean_is_main_admin_only(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    _log(db, acme["_id"])
    admin = make_user("local_admin", "acme-admin", acme["_id"])
    _login(client, make_token, admin)

    assert client.delete("/api/audit/logs").status_code == 403
    assert db.audit_logs.count_documents({}) == 1


def test_audit_page_has_clean_button_in_card_header(client, make_token, make_user):
    root = make_user("main_admin", "root")
    _login(client, make_token, root)

    body = client.get("/audit").get_data(as_text=True)

    assert "card-header d-flex justify-content-between align-items-center" in body
    assert "cleanAudit()" in body
    assert 'id="cleanAuditModal"' in body
    assert "submitCleanAudit(event)" in body
    assert "confirm(" not in body
