from pathlib import Path

import pytest

from app.page_registry import BASE_MODALS, MODALS, PAGES, SHARED_MODALS, catalogue_summary, page_info

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
TEMPLATES = BACKEND_DIR / "app" / "templates"


@pytest.fixture(scope="module")
def flask_app():
    from app import create_app

    return create_app()


def _template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_every_registered_page_is_a_flask_endpoint(flask_app):
    endpoints = {rule.endpoint for rule in flask_app.url_map.iter_rules()}
    assert set(PAGES) <= endpoints


def test_page_and_modal_ids_are_unique():
    page_ids = [page["id"] for page in PAGES.values()]
    modal_ids = [modal["id"] for modal in MODALS.values()]
    assert len(page_ids) == len(set(page_ids))
    assert len(modal_ids) == len(set(modal_ids))
    assert not set(page_ids) & set(modal_ids)
    assert catalogue_summary() == {"pages": len(PAGES), "modals": len(MODALS)}


def test_page_templates_exist_and_declare_their_own_modals():
    for endpoint, page in PAGES.items():
        source = _template(page["template"])
        assert source, endpoint
        for modal in page["modals"]:
            assert modal in MODALS, f"{endpoint} references unknown modal {modal}"
            assert f'id="{MODALS[modal]["element"]}"' in source, (
                f"{endpoint} does not render #{MODALS[modal]['element']}"
            )


def test_shared_modals_live_in_the_dashboard_layout():
    source = _template("dashboard_base.html")
    for modal in SHARED_MODALS:
        assert f'id="{MODALS[modal]["element"]}"' in source


def test_base_modals_live_in_the_base_template():
    source = _template("base.html")
    for modal in BASE_MODALS:
        assert f'id="{MODALS[modal]["element"]}"' in source


def test_every_modal_records_an_existing_form_id():
    sources = {path.name: path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*.html")}
    form_ids = []
    for key, modal in MODALS.items():
        assert "form" in modal, key
        if modal["form"] is None:
            continue
        form_ids.append(modal["form"])
        hosts = [src for src in sources.values() if f'id="{modal["element"]}"' in src]
        assert hosts, f"{key} is not rendered by any template"
        assert any(f'id="{modal["form"]}"' in src for src in hosts), (
            f"{key} does not render its form #{modal['form']}"
        )

    # A form id is used once and never doubles as a modal element id.
    assert len(form_ids) == len(set(form_ids))
    assert not set(form_ids) & {modal["element"] for modal in MODALS.values()}


def test_page_info_resolves_endpoints_and_expands_modals():
    assert page_info("unknown_endpoint") is None

    login = page_info("login_page")
    assert login["id"] == "PG-LOGIN"

    tasks = page_info("tasks_page")
    modal_elements = [modal["element"] for modal in tasks["modals"]]
    assert "taskDetailModal" in modal_elements
    assert "taskEditModal" in modal_elements
    assert set(SHARED_MODALS) <= set(modal_elements)
    assert set(BASE_MODALS) <= set(modal_elements)

    # The settings dialog is rendered by base.html, so the auth pages carry it
    # too even though they have no dashboard dialogs.
    assert [modal["element"] for modal in login["modals"]] == list(BASE_MODALS)


def test_footer_badge_renders_the_page_id(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    client.set_cookie("access_token", make_token(admin))

    response = client.get("/tasks")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="page-id" content="PG-TASKS"' in body
    assert "page-id-badge" in body
    assert 'id="pageInfoModal"' in body
    assert 'id="taskEditModal"' in body

    # The shared three-column footer: name, settings + database icons, badges.
    assert 'class="footer app-footer' in body
    assert 'id="db-status"' in body
    assert 'id="settingsModal"' in body
    assert 'data-bs-target="#settingsModal"' in body
    assert "bi bi-gear" in body
    assert "bi bi-database-fill" in body
    assert "set-language" in body
    assert 'name="lang"' in body
    # The badge is the page id alone; the old "Page Information" label is gone.
    assert ">PG-TASKS<" in body
    assert "Page Information" not in body
    assert "Page information" not in body
    # Share / copy / screenshot actions sit next to the dialog's close button.
    assert 'id="pageInfoShare"' in body
    assert 'id="pageInfoCopy"' in body
    assert 'id="pageInfoScreenshot"' in body
    assert "html2canvas" in body
    assert "version-badge" in body


def test_companies_actions_are_circular_and_include_edit(client, make_token, make_user):
    admin = make_user("main_admin", "root")
    client.set_cookie("access_token", make_token(admin))

    body = client.get("/companies").get_data(as_text=True)

    # table-actions rounds every button in the action column.
    assert 'class="table-actions"' in body
    assert "editCompany(" in body
    assert 'id="companyModalTitle"' in body
    assert "saveCompany(event)" in body


def test_customers_actions_include_view_and_history(client, make_token, make_user, make_company):
    company = make_company("Acme", "acme")
    admin = make_user("local_admin", "acme-admin", company["_id"])
    client.set_cookie("access_token", make_token(admin))

    body = client.get("/customers").get_data(as_text=True)

    # Action column rounds every button; each row offers view and history.
    assert 'class="table-actions text-center"' in body
    assert "/customers/${c._id}" in body
    assert "bi bi-eye" in body
    assert "showCustomerHistory(" in body
    assert "bi bi-clock-history" in body
    assert 'id="customerHistoryModal"' in body
    assert 'id="customerHistoryTitle"' in body
    assert "editCustomer(" in body


def test_language_switch_remembers_the_choice_and_returns_to_the_page(client):
    response = client.get("/set-language?lang=fr&next=/tasks?status=open")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tasks?status=open")
    assert "lang=fr" in response.headers["Set-Cookie"]

    # An absolute or scheme-relative next target is never trusted.
    response = client.get("/set-language?lang=ar&next=//evil.example")
    assert response.headers["Location"].endswith("/dashboard")
