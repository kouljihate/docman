from datetime import datetime, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def test_local_admin_only_lists_own_company_customers(
    client, db, make_token, make_user, make_company
):
    acme = make_company("Acme", "acme")
    beta = make_company("Beta", "beta")
    admin = make_user("local_admin", "acme-admin", acme["_id"])
    make_user("customer", "acme-customer", acme["_id"])
    make_user("customer", "beta-customer", beta["_id"])

    _login(client, make_token, admin)
    payload = client.get("/api/customers/").get_json()
    usernames = [c["username"] for c in payload]
    assert usernames == ["acme-customer"]


def test_cross_company_document_access_denied(
    client, db, make_token, make_user, make_company, tmp_path
):
    acme = make_company("Acme", "acme")
    beta = make_company("Beta", "beta")
    admin = make_user("local_admin", "acme-admin", acme["_id"])
    beta_customer = make_user("customer", "beta-customer", beta["_id"])

    pdf = tmp_path / "beta.pdf"
    pdf.write_bytes(b"%PDF-1.4 beta")
    doc_id = ObjectId()
    db.documents.insert_one(
        {
            "_id": doc_id,
            "company_id": beta["_id"],
            "customer_id": beta_customer["_id"],
            "service_id": ObjectId(),
            "original_name": "beta.pdf",
            "stored_path": str(pdf),
            "file_size": 10,
            "mime_type": "application/pdf",
            "uploaded_by": ObjectId(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    _login(client, make_token, admin)
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get(f"/api/documents/{doc_id}/file").status_code == 404


def test_employee_cannot_manage_customers(client, make_token, make_user, make_company):
    company = make_company()
    employee = make_user("local_employee", "emp", company["_id"])
    _login(client, make_token, employee)
    assert client.get("/api/customers/").status_code == 403
    assert client.get("/api/companies/").status_code == 403


def test_customer_cannot_open_admin_pages(client, make_token, make_user, make_company):
    company = make_company()
    customer = make_user("customer", "cust", company["_id"])
    _login(client, make_token, customer)
    assert client.get("/users").status_code == 403
    assert client.get("/documents").status_code == 403
    assert client.get("/my-space").status_code == 200


def test_main_admin_can_create_and_list_companies(client, make_token, make_user):
    main = make_user("main_admin", "root")
    _login(client, make_token, main)

    created = client.post(
        "/api/companies/",
        json={
            "company_name": "Gamma",
            "code": "gamma",
            "admin_username": "gamma-admin",
            "admin_email": "gamma-admin@example.com",
            "admin_password": "secret123",
            "admin_full_name": "Gamma Admin",
        },
    )
    assert created.status_code == 201
    assert created.get_json()["company_name"] == "Gamma"

    listed = client.get("/api/companies/").get_json()
    assert [c["company_name"] for c in listed] == ["Gamma"]


def test_local_admin_cannot_create_companies(client, make_token, make_user, make_company):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)
    resp = client.post("/api/companies/", json={"company_name": "Rogue"})
    assert resp.status_code == 403


def test_customer_request_is_routed_to_own_local_admin(
    client, db, make_token, make_user, make_company
):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "cust", company["_id"])
    db.users.update_one({"_id": customer["_id"]}, {"$set": {"local_admin_id": admin["_id"]}})

    _login(client, make_token, customer)
    resp = client.post(
        "/api/requests/",
        data={"title": "Please fix my statement", "content": "Details here"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201

    stored = db.requests.find_one({"title": "Please fix my statement"})
    assert stored["company_id"] == company["_id"]
    assert stored["target_admin_id"] == admin["_id"]
    assert stored["created_by"] == customer["_id"]

    # Another company's admin cannot see it.
    other_company = make_company("Beta", "beta")
    stranger = make_user("local_admin", "beta-admin", other_company["_id"])
    _login(client, make_token, stranger)
    assert client.get("/api/requests/").get_json() == []


def test_audit_logs_are_main_admin_only(client, make_token, make_user, make_company):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    main = make_user("main_admin", "root")

    _login(client, make_token, admin)
    assert client.get("/api/audit/logs").status_code == 403

    _login(client, make_token, main)
    assert client.get("/api/audit/logs").status_code == 200
