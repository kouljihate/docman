"""Roles, company (tenant) scoping and access decorators.

Four profiles exist:

- ``main_admin``    - platform owner: companies, global dashboard, audit logs.
- ``local_admin``   - manages one company: its users, customers, services,
                      documents, tasks, activities, messaging and reports.
- ``local_employee``- company staff: tasks, activities, documents, reports,
                      messaging, notifications and requests.
- ``customer``      - sees only their own affairs/activities/documents and
                      raises requests to their own local admin.
"""
from functools import wraps

from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity

MAIN_ADMIN = "main_admin"
LOCAL_ADMIN = "local_admin"
LOCAL_EMPLOYEE = "local_employee"
CUSTOMER = "customer"

ALL_ROLES = (MAIN_ADMIN, LOCAL_ADMIN, LOCAL_EMPLOYEE, CUSTOMER)
COMPANY_ROLES = (LOCAL_ADMIN, LOCAL_EMPLOYEE, CUSTOMER)
STAFF_ROLES = (MAIN_ADMIN, LOCAL_ADMIN)
LOCAL_STAFF_ROLES = (LOCAL_ADMIN, LOCAL_EMPLOYEE)

# Roles stored by older versions; still accepted so existing tokens and
# unmigrated records keep working.
LEGACY_ROLES = {
    "admin": LOCAL_ADMIN,
    "employee": LOCAL_EMPLOYEE,
}


def normalize_role(value):
    role = (value or "").strip().lower()
    return LEGACY_ROLES.get(role, role)


def current_role():
    return normalize_role(get_jwt().get("role"))


def current_user_id():
    return get_jwt_identity()


def to_object_id(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


def current_company_id():
    raw = get_jwt().get("company_id")
    if not raw:
        return None
    return to_object_id(raw)


def is_main_admin():
    return current_role() == MAIN_ADMIN


def is_local_admin():
    return current_role() == LOCAL_ADMIN


def is_local_employee():
    return current_role() == LOCAL_EMPLOYEE


def is_customer():
    return current_role() == CUSTOMER


def is_staff():
    return current_role() in STAFF_ROLES


def is_company_staff():
    return current_role() in LOCAL_STAFF_ROLES


def company_scope(query=None):
    """Merge the caller's company filter into a Mongo query.

    The main admin is not tied to a company and sees every tenant (used by
    platform-level views); everyone else is restricted to their own company.
    A company-less token matches nothing.
    """
    scoped = dict(query or {})
    if is_main_admin():
        return scoped
    company_id = current_company_id()
    if company_id is None:
        scoped["_id"] = {"$in": []}
        return scoped
    scoped["company_id"] = company_id
    return scoped


def same_company(document):
    if document is None:
        return False
    if is_main_admin():
        return True
    company_id = current_company_id()
    return company_id is not None and document.get("company_id") == company_id


def tenant_fields():
    """Fields to stamp on new tenant-owned documents."""
    return {"company_id": current_company_id()}


def role_required(*allowed):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if current_role() not in allowed:
                return jsonify({"error": "Forbidden"}), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator


# Shared decorators (use after @jwt_required()).
main_admin_required = role_required(MAIN_ADMIN)
admin_required = role_required(MAIN_ADMIN, LOCAL_ADMIN)
local_admin_required = role_required(LOCAL_ADMIN)
local_staff_required = role_required(LOCAL_ADMIN, LOCAL_EMPLOYEE)
company_member_required = role_required(*COMPANY_ROLES)
