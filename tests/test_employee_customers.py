"""The customer directory is readable by a local employee, read-only."""


def _login(client, make_token, user):
    client.set_cookie("access_token", make_token(user))


def test_employee_opens_the_customers_menu(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    _login(client, make_token, employee)

    response = client.get("/customers")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # The navigation entry is there, and the page is the customer directory.
    assert 'href="/customers"' in body
    assert 'data-page-id="PG-CUSTOMERS"' in body or "PG-CUSTOMERS" in body

    detail = client.get("/customers/000000000000000000000000")
    assert detail.status_code == 200


def test_employee_lists_the_customers_of_their_company(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    other = make_company("Beta", "beta")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    mine = make_user("customer", "acme-customer", company["_id"])
    make_user("customer", "beta-customer", other["_id"])
    _login(client, make_token, employee)

    response = client.get("/api/customers/")

    assert response.status_code == 200
    assert [customer["_id"] for customer in response.get_json()] == [str(mine["_id"])]


def test_employee_cannot_create_edit_or_delete_customers(
    client, db, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    customer = make_user("customer", "acme-customer", company["_id"])
    _login(client, make_token, employee)

    created = client.post(
        "/api/customers/",
        json={
            "username": "new-customer",
            "email": "new@example.com",
            "full_name": "New Customer",
            "password": "secret123",
        },
    )
    assert created.status_code == 403

    updated = client.put(f"/api/customers/{customer['_id']}", json={"full_name": "Renamed"})
    assert updated.status_code == 403

    deleted = client.delete(f"/api/customers/{customer['_id']}")
    assert deleted.status_code == 403

    assert db.users.count_documents({"role": "customer"}) == 1


def test_employee_page_hides_the_admin_buttons(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    employee = make_user("local_employee", "acme-employee", company["_id"])
    _login(client, make_token, employee)

    body = client.get("/customers").get_data(as_text=True)

    # The buttons are gone; the function definitions alone are harmless.
    assert 'onclick="openCreateModal()"' not in body
    assert 'onclick="openBulkModal()"' not in body
    assert "onclick=\"editCustomer('" not in body
    assert 'onclick="deleteCustomer(' not in body
    assert 'href="/customers/${c._id}"' in body


def test_local_admin_keeps_the_customer_admin_buttons(
    client, make_token, make_user, make_company
):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    _login(client, make_token, admin)

    body = client.get("/customers").get_data(as_text=True)

    assert 'onclick="openCreateModal()"' in body
    assert 'onclick="openBulkModal()"' in body
    assert "onclick=\"editCustomer('" in body
    assert 'onclick="deleteCustomer(' in body
