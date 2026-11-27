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
    # Employees read the directory (their menu has it) but never change it.
    assert client.get("/api/customers/").status_code == 200
    assert client.post("/api/customers/", json={}).status_code == 403
    assert client.delete("/api/customers/000000000000000000000000").status_code == 403
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

    listed = client.get("/api/companies/").get_json()["items"]
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


def test_main_admin_manages_users_of_every_company(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    beta = make_company("Beta", "beta")
    make_user("local_admin", "acme-admin", acme["_id"])
    make_user("local_employee", "acme-emp", acme["_id"])
    make_user("customer", "beta-customer", beta["_id"])
    main = make_user("main_admin", "root")
    other_main = make_user("main_admin", "root2")

    _login(client, make_token, main)
    listed = client.get("/api/users/").get_json()
    usernames = {u["username"] for u in listed}
    assert usernames == {"acme-admin", "acme-emp", "beta-customer"}

    # Main admins are not manageable through the tenant user API.
    assert client.get(f"/api/users/{other_main['_id']}").status_code == 404
    assert client.delete(f"/api/users/{other_main['_id']}").status_code == 404

    created = client.post(
        "/api/users/",
        json={
            "username": "beta-admin",
            "email": "beta-admin@example.com",
            "password": "secret123",
            "full_name": "Beta Admin",
            "role": "local_admin",
            "company_id": str(beta["_id"]),
        },
    )
    assert created.status_code == 201
    assert created.get_json()["company_id"] == str(beta["_id"])

    filtered = client.get(f"/api/users/?company_id={beta['_id']}").get_json()
    assert {u["username"] for u in filtered} == {"beta-customer", "beta-admin"}

    assert client.get("/users").status_code == 200


def test_local_admin_cannot_create_local_admin(client, make_token, make_user, make_company):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)
    resp = client.post(
        "/api/users/",
        json={
            "username": "new-admin",
            "email": "new-admin@example.com",
            "password": "secret123",
            "full_name": "New Admin",
            "role": "local_admin",
        },
    )
    assert resp.status_code == 403


def test_audit_logs_are_main_admin_only(client, make_token, make_user, make_company):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    main = make_user("main_admin", "root")

    _login(client, make_token, admin)
    assert client.get("/api/audit/logs").status_code == 403

    _login(client, make_token, main)
    assert client.get("/api/audit/logs").status_code == 200


def test_company_creation_stores_moroccan_legal_information(client, make_token, make_user):
    main = make_user("main_admin", "root")
    _login(client, make_token, main)

    logo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    created = client.post(
        "/api/companies/",
        json={
            "company_name": "Atlas Conseil",
            "code": "atlas",
            "legal_form": "SARL AU",
            "ice": "001234567000045",
            "rc": "RC Casablanca 123456",
            "tax_id": "12345678",
            "patente": "35791124",
            "cnss": "1234567",
            "capital": "100 000",
            "address": "12 rue des Fleurs",
            "city": "Casablanca",
            "region": "Casablanca-Settat",
            "postal_code": "20000",
            "email": "contact@atlas.ma",
            "phone": "+212 5 22 00 00 00",
            "website": "https://atlas.ma",
            "logo": logo,
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["ice"] == "001234567000045"
    assert body["legal_form"] == "SARL AU"
    assert body["rc"] == "RC Casablanca 123456"
    assert body["patente"] == "35791124"
    assert body["cnss"] == "1234567"
    assert body["capital"] == "100 000"
    assert body["city"] == "Casablanca"
    assert body["region"] == "Casablanca-Settat"
    assert body["postal_code"] == "20000"
    assert body["country"] == "Maroc"
    assert body["website"] == "https://atlas.ma"
    assert body["logo"] == logo


def test_company_creation_rejects_invalid_ice(client, make_token, make_user):
    main = make_user("main_admin", "root")
    _login(client, make_token, main)

    resp = client.post(
        "/api/companies/",
        json={"company_name": "Bad ICE", "ice": "12345"},
    )
    assert resp.status_code == 400
    assert "ICE" in resp.get_json()["error"]


def test_company_settings_keep_logo_when_not_resubmitted(
    client, db, make_token, make_user, make_company
):
    company = make_company()
    logo = "data:image/png;base64,iVBORw0KGgo="
    db.companies.update_one({"_id": company["_id"]}, {"$set": {"logo": logo, "ice": "001234567000045"}})
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    resp = client.post("/api/company/settings", json={"company_name": "Acme Renamed"})
    assert resp.status_code == 200
    saved = db.companies.find_one({"_id": company["_id"]})
    assert saved["company_name"] == "Acme Renamed"
    assert saved["logo"] == logo
    assert saved["ice"] == "001234567000045"


def test_customer_creation_stores_cin_and_photo_id(
    client, make_token, make_user, make_company
):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    photo = "data:image/png;base64,iVBORw0KGgo="
    created = client.post(
        "/api/customers/",
        json={
            "username": "cin-customer",
            "email": "cin-customer@example.com",
            "password": "secret123",
            "full_name": "CIN Customer",
            "cin": "ab123456",
            "photo_id": photo,
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["cin"] == "AB123456"
    assert body["photo_id"] == photo

    listed = client.get("/api/customers/").get_json()
    assert listed[0]["cin"] == "AB123456"
    assert listed[0]["photo_id"] == photo

    updated = client.put(f"/api/customers/{body['_id']}", json={"cin": "CD987654"})
    assert updated.status_code == 200
    assert updated.get_json()["cin"] == "CD987654"
    assert updated.get_json()["photo_id"] == photo


def test_customer_photo_id_rejects_non_image(client, make_token, make_user, make_company):
    company = make_company()
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    resp = client.post(
        "/api/customers/",
        json={
            "username": "bad-photo",
            "email": "bad-photo@example.com",
            "password": "secret123",
            "full_name": "Bad Photo",
            "cin": "AB123456",
            "photo_id": "javascript:alert(1)",
        },
    )
    assert resp.status_code == 400
    assert "Photo ID" in resp.get_json()["error"]
