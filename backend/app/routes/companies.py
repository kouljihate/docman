"""Platform-level company management (main admin) and company lookup."""
import re
from datetime import datetime, timezone

from bcrypt import gensalt, hashpw
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import get_db
from app.models.company import (
    CompanyAdminCreate,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
)
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    current_company_id,
    current_user_id,
    main_admin_required,
    role_required,
)

companies_bp = Blueprint("companies", __name__, url_prefix="/api/companies")

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 200


@companies_bp.route("/public", methods=["GET"])
def public_companies():
    """Active companies, for the public sign-up company picker."""
    db = get_db()
    companies = db.companies.find({"is_active": True}, {"company_name": 1, "code": 1}).sort("company_name", 1)
    return jsonify([{"_id": str(c["_id"]), "company_name": c.get("company_name", ""), "code": c.get("code", "")} for c in companies]), 200


COUNT_KEYS = (
    "admins_count",
    "employees_count",
    "customers_count",
    "affairs_count",
    "documents_count",
    "tasks_count",
)


def _company_counts(db, company_ids):
    """Per-company counters for many companies in a single aggregation.

    The list page shows six counters per row; counting them one row at a time
    costs six queries per company. Instead every requested tenant is looked up
    once and the counters are computed server-side in one command.
    """
    ids = list(company_ids)
    if not ids:
        return {}

    def users_with_role(role):
        return {
            "$size": {
                "$filter": {
                    "input": "$tenant_users",
                    "as": "user",
                    "cond": {"$eq": ["$$user.role", role]},
                }
            }
        }

    pipeline = [
        {"$match": {"_id": {"$in": ids}}},
        *[
            {
                "$lookup": {
                    "from": collection,
                    "localField": "_id",
                    "foreignField": "company_id",
                    "as": f"tenant_{collection}",
                }
            }
            for collection in ("users", "affairs", "documents", "tasks")
        ],
        {
            "$project": {
                "admins_count": users_with_role(LOCAL_ADMIN),
                "employees_count": users_with_role(LOCAL_EMPLOYEE),
                "customers_count": users_with_role(CUSTOMER),
                "affairs_count": {"$size": "$tenant_affairs"},
                "documents_count": {"$size": "$tenant_documents"},
                "tasks_count": {"$size": "$tenant_tasks"},
            }
        },
    ]
    return {doc["_id"]: doc for doc in db.companies.aggregate(pipeline)}


def _counts_for(db, company_id):
    return _company_counts(db, [company_id]).get(company_id, {})


def _serialize(company, counts=None):
    data = CompanyResponse.from_mongo(company).model_dump(by_alias=True)
    counts = counts or {}
    for key in COUNT_KEYS:
        data[key] = counts.get(key, 0)
    return data


def _positive_int_arg(name, default, maximum=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum) if maximum else value


@companies_bp.route("/", methods=["GET"])
@jwt_required()
@main_admin_required
def list_companies():
    """One page of companies, with their counters, for the platform admin.

    ``GET /api/companies/?page=2&per_page=25`` returns
    ``{"items": [...], "page": 2, "per_page": 25, "total": 102, "pages": 5}``.
    """
    db = get_db()
    search = request.args.get("q", "").strip()
    page = _positive_int_arg("page", 1)
    per_page = _positive_int_arg("per_page", DEFAULT_PER_PAGE, MAX_PER_PAGE)
    query = {}
    if search:
        query["company_name"] = {"$regex": re.escape(search), "$options": "i"}

    total = db.companies.count_documents(query)
    pages = max(1, (total + per_page - 1) // per_page)
    # Deleting or filtering can leave the caller past the last page.
    page = min(page, pages)
    companies = list(
        db.companies.find(query)
        .sort("company_name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    counts = _company_counts(db, [company["_id"] for company in companies])
    return (
        jsonify(
            {
                "items": [_serialize(c, counts.get(c["_id"])) for c in companies],
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
            }
        ),
        200,
    )


@companies_bp.route("/", methods=["POST"])
@jwt_required()
@main_admin_required
def create_company():
    db = get_db()
    try:
        payload = CompanyCreate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if db.companies.find_one({"company_name": payload.company_name}):
        return jsonify({"error": "A company with this name already exists"}), 409

    now = datetime.now(timezone.utc)
    data = payload.model_dump(exclude={"admin_username", "admin_email", "admin_password", "admin_full_name"})
    data["created_at"] = now
    data["updated_at"] = now
    data["created_by"] = ObjectId(current_user_id())
    result = db.companies.insert_one(data)
    company_id = result.inserted_id

    admin_created = None
    if payload.admin_username and payload.admin_email and payload.admin_password:
        if db.users.find_one({"$or": [{"username": payload.admin_username}, {"email": str(payload.admin_email)}]}):
            return jsonify({"error": "Company created but admin username/email already exists"}), 409
        admin_doc = {
            "username": payload.admin_username,
            "email": str(payload.admin_email),
            "password": hashpw(payload.admin_password.encode("utf-8"), gensalt()).decode("utf-8"),
            "role": "local_admin",
            "full_name": payload.admin_full_name or payload.admin_username,
            "phone": None,
            "is_active": True,
            "company_id": company_id,
            "created_by": ObjectId(current_user_id()),
            "created_at": now,
            "updated_at": now,
        }
        admin_id = db.users.insert_one(admin_doc).inserted_id
        admin_created = {"_id": str(admin_id), "username": admin_doc["username"]}

    AuditService.log(
        action="create",
        entity_type="company",
        entity_id=str(company_id),
        performed_by=current_user_id(),
        description=f"Company '{payload.company_name}' created",
        company_id=company_id,
    )

    created = db.companies.find_one({"_id": company_id})
    response = _serialize(created, _counts_for(db, company_id))
    if admin_created:
        response["admin"] = admin_created
    return jsonify(response), 201


@companies_bp.route("/current", methods=["GET"])
@jwt_required()
@role_required("local_admin", "local_employee", "customer")
def current_company():
    db = get_db()
    company_id = current_company_id()
    company = db.companies.find_one({"_id": company_id}) if company_id else None
    if not company:
        return jsonify({"error": "Company not found"}), 404
    return jsonify(CompanyResponse.from_mongo(company).model_dump(by_alias=True)), 200


@companies_bp.route("/<company_id>", methods=["GET"])
@jwt_required()
@main_admin_required
def get_company(company_id):
    db = get_db()
    company = db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        return jsonify({"error": "Company not found"}), 404
    data = _serialize(company, _counts_for(db, company["_id"]))
    data["admins"] = [
        {"_id": str(u["_id"]), "username": u["username"], "email": u.get("email"), "full_name": u.get("full_name")}
        for u in db.users.find({"company_id": company["_id"], "role": "local_admin"}).sort("full_name", 1)
    ]
    return jsonify(data), 200


@companies_bp.route("/<company_id>", methods=["PUT"])
@jwt_required()
@main_admin_required
def update_company(company_id):
    db = get_db()
    company = db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        return jsonify({"error": "Company not found"}), 404

    try:
        payload = CompanyUpdate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        return jsonify({"error": "No fields to update"}), 400
    update["updated_at"] = datetime.now(timezone.utc)
    db.companies.update_one({"_id": company["_id"]}, {"$set": update})

    AuditService.log(
        action="update",
        entity_type="company",
        entity_id=company_id,
        performed_by=current_user_id(),
        description=f"Company '{company.get('company_name')}' updated",
        company_id=company["_id"],
    )
    return jsonify(_serialize(db.companies.find_one({"_id": company["_id"]}), _counts_for(db, company["_id"]))), 200


@companies_bp.route("/<company_id>/admins", methods=["POST"])
@jwt_required()
@main_admin_required
def create_company_admin(company_id):
    db = get_db()
    company = db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        return jsonify({"error": "Company not found"}), 404

    try:
        payload = CompanyAdminCreate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if db.users.find_one({"$or": [{"username": payload.username}, {"email": str(payload.email)}]}):
        return jsonify({"error": "Username or email already exists"}), 409

    now = datetime.now(timezone.utc)
    admin_id = db.users.insert_one(
        {
            "username": payload.username,
            "email": str(payload.email),
            "password": hashpw(payload.password.encode("utf-8"), gensalt()).decode("utf-8"),
            "role": "local_admin",
            "full_name": payload.full_name,
            "phone": payload.phone,
            "is_active": True,
            "company_id": company["_id"],
            "created_by": ObjectId(current_user_id()),
            "created_at": now,
            "updated_at": now,
        }
    ).inserted_id

    AuditService.log(
        action="create",
        entity_type="user",
        entity_id=str(admin_id),
        performed_by=current_user_id(),
        description=f"Local admin '{payload.username}' created for {company.get('company_name')}",
        company_id=company["_id"],
    )
    return (
        jsonify(
            {
                "_id": str(admin_id),
                "username": payload.username,
                "email": str(payload.email),
                "full_name": payload.full_name,
                "role": "local_admin",
                "company_id": str(company["_id"]),
            }
        ),
        201,
    )


@companies_bp.route("/<company_id>", methods=["DELETE"])
@jwt_required()
@main_admin_required
def delete_company(company_id):
    db = get_db()
    company = db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        return jsonify({"error": "Company not found"}), 404

    for collection in ("documents", "tasks", "activities", "affairs", "services", "notifications", "requests", "audit_logs"):
        db[collection].delete_many({"company_id": company["_id"]})
    db.users.delete_many({"company_id": company["_id"]})
    db.companies.delete_one({"_id": company["_id"]})

    AuditService.log(
        action="delete",
        entity_type="company",
        entity_id=company_id,
        performed_by=current_user_id(),
        description=f"Company '{company.get('company_name')}' deleted with all its data",
        company_id=company["_id"],
    )
    return jsonify({"message": "Company deleted"}), 200
