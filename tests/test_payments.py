from datetime import datetime, timedelta, timezone

from bson import ObjectId


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def _payment(company_id, customer_id, created_by, **extra):
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "company_id": company_id,
        "customer_id": customer_id,
        "label": "Facture 2026-014",
        "amount": 1200.0,
        "currency": "MAD",
        "due_date": now + timedelta(days=3),
        "status": "pending",
        "paid_at": None,
        "method": "transfer",
        "notes": None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    return doc


def test_local_admin_creates_and_lists_customer_payments(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    _login(client, make_token, admin)

    response = client.post(
        "/api/payments/",
        json={
            "customer_id": str(customer["_id"]),
            "label": "Facture 2026-014",
            "amount": 2500,
            "currency": "MAD",
            "due_date": "2026-12-05",
            "method": "transfer",
        },
    )
    assert response.status_code == 201, response.get_json()
    created = response.get_json()
    assert created["customer_name"] == "Acme-Customer"
    assert created["display_status"] == "pending"

    listing = client.get("/api/payments/").get_json()
    assert len(listing) == 1
    assert listing[0]["customer_id"] == str(customer["_id"])
    assert listing[0]["company_id"] == str(company["_id"])

    # The payment dialog's customer picker only offers real customers.
    options = client.get("/api/customers/").get_json()
    assert [c["_id"] for c in options] == [str(customer["_id"])]


def test_pending_payment_past_due_is_reported_overdue(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    db.payments.insert_one(
        _payment(company["_id"], customer["_id"], admin["_id"],
                 due_date=datetime.now(timezone.utc) - timedelta(days=2))
    )
    _login(client, make_token, admin)

    payments = client.get("/api/payments/").get_json()
    assert payments[0]["is_overdue"] is True
    assert payments[0]["display_status"] == "overdue"


def test_marking_a_payment_paid_stamps_the_date(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    payment = _payment(company["_id"], customer["_id"], admin["_id"])
    db.payments.insert_one(payment)
    _login(client, make_token, admin)

    response = client.put(f"/api/payments/{payment['_id']}", json={"status": "paid"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "paid"
    assert response.get_json()["paid_at"] is not None
    assert response.get_json()["display_status"] == "paid"
    assert db.payments.find_one({"_id": payment["_id"]})["paid_at"] is not None


def test_payments_are_scoped_to_the_local_admin_company(client, db, make_token, make_user, make_company):
    acme = make_company("Acme", "acme")
    other = make_company("Other", "other")
    acme_admin = make_user("local_admin", "acme-admin", acme["_id"])
    acme_customer = make_user("customer", "acme-customer", acme["_id"])
    other_admin = make_user("local_admin", "other-admin", other["_id"])
    other_customer = make_user("customer", "other-customer", other["_id"])
    foreign = _payment(other["_id"], other_customer["_id"], other_admin["_id"])
    db.payments.insert_one(foreign)

    _login(client, make_token, acme_admin)
    assert client.get("/api/payments/").get_json() == []
    assert client.get(f"/api/payments/{foreign['_id']}").status_code == 404
    assert client.delete(f"/api/payments/{foreign['_id']}").status_code == 404
    assert db.payments.count_documents({}) == 1

    # A payment cannot be attached to a customer of another company.
    response = client.post(
        "/api/payments/",
        json={
            "customer_id": str(other_customer["_id"]),
            "amount": 100,
            "due_date": "2026-12-05",
        },
    )
    assert response.status_code == 400

    # The other company still sees its own payment.
    _login(client, make_token, other_admin)
    assert len(client.get("/api/payments/").get_json()) == 1


def test_payments_are_local_admin_only(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    main_admin = make_user("main_admin", "root")
    _payment(company["_id"], customer["_id"], employee["_id"])
    for user in (employee, customer, main_admin):
        _login(client, make_token, user)
        assert client.get("/api/payments/").status_code == 403
        assert client.get("/payments").status_code == 403

    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)
    page = client.get("/payments")
    assert page.status_code == 200
    assert 'name="page-id" content="PG-PAYMENTS"' in page.get_data(as_text=True)


def test_dashboard_alerts_the_local_admin_about_due_payments(client, db, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    now = datetime.now(timezone.utc)
    db.payments.insert_one(
        _payment(company["_id"], customer["_id"], admin["_id"], due_date=now - timedelta(days=1))
    )
    db.payments.insert_one(
        _payment(company["_id"], customer["_id"], admin["_id"], due_date=now + timedelta(days=2))
    )
    # Paid and far-future payments are not alerts.
    db.payments.insert_one(
        _payment(company["_id"], customer["_id"], admin["_id"], status="paid", due_date=now - timedelta(days=5))
    )
    db.payments.insert_one(
        _payment(company["_id"], customer["_id"], admin["_id"], due_date=now + timedelta(days=30))
    )
    _login(client, make_token, admin)

    stats = client.get("/api/dashboard/stats").get_json()
    assert stats["payments_due_count"] == 2
    assert stats["payments_overdue_count"] == 1

    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="paymentAlert"' in body
