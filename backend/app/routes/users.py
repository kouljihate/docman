from datetime import datetime, timezone

from bcrypt import gensalt, hashpw
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import get_db
from app.models.user import UserCreate, UserResponse, UserUpdate
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    admin_required,
    company_scope,
    current_company_id,
    current_user_id,
    is_main_admin,
    normalize_role,
    to_object_id,
)

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

# Roles a local admin may hand out inside their own company.
LOCAL_MANAGED_ROLES = (LOCAL_EMPLOYEE, CUSTOMER)
# The main admin manages every tenant user (local admins, employees and
# customers) across companies. Other main admins are never editable here.
MANAGED_ROLES = (LOCAL_ADMIN, LOCAL_EMPLOYEE, CUSTOMER)


def _allowed_roles():
    return MANAGED_ROLES if is_main_admin() else LOCAL_MANAGED_ROLES


def _managed_query(extra=None):
    query = company_scope(extra)
    roles = _allowed_roles()
    query["role"] = {"$in": [role for role in roles]}
    return query


def _company_exists(company_id):
    return bool(company_id) and get_db().companies.find_one({"_id": company_id}) is not None


def _fallback_local_admin(db, company_id):
    admin = db.users.find_one(
        {"company_id": company_id, "role": LOCAL_ADMIN, "is_active": True},
        sort=[("created_at", 1)],
    )
    return admin["_id"] if admin else None


@users_bp.route("/", methods=["GET"])
@jwt_required()
@admin_required
def list_users():
    db = get_db()
    role = normalize_role(request.args.get("role"))
    status = request.args.get("status")

    query = _managed_query()
    if role and role in _allowed_roles():
        query["role"] = role
    if status == "active":
        query["is_active"] = True
    elif status == "inactive":
        query["is_active"] = False

    if is_main_admin():
        company_id = to_object_id(request.args.get("company_id"))
        if company_id:
            query["company_id"] = company_id

    from flask_jwt_extended import get_jwt
    users = list(db.users.find(query).sort("created_at", -1))
    return jsonify([UserResponse(**u).model_dump(by_alias=True) for u in users]), 200


@users_bp.route("/", methods=["POST"])
@jwt_required()
@admin_required
def create_user():
    db = get_db()
    data = request.get_json(silent=True) or {}

    requested_role = normalize_role(data.get("role", LOCAL_EMPLOYEE))
    if requested_role not in _allowed_roles():
        return jsonify({"error": "Role cannot be assigned here"}), 403

    try:
        user_data = UserCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if is_main_admin():
        company_id = to_object_id(data.get("company_id"))
        if not _company_exists(company_id):
            return jsonify({"error": "A valid company is required"}), 400
    else:
        company_id = current_company_id()
        if company_id is None:
            return jsonify({"error": "Your account is not attached to a company"}), 400

    if db.users.find_one({"$or": [{"username": user_data.username}, {"email": str(user_data.email)}]}):
        return jsonify({"error": "Username or email already exists"}), 409

    now = datetime.now(timezone.utc)
    user_dict = user_data.model_dump(by_alias=True)
    user_dict["role"] = requested_role
    user_dict["company_id"] = company_id
    user_dict["created_by"] = ObjectId(current_user_id())
    user_dict["password"] = hashpw(user_dict["password"].encode("utf-8"), gensalt()).decode("utf-8")
    user_dict["created_at"] = now
    user_dict["updated_at"] = now
    if requested_role == CUSTOMER:
        if is_main_admin():
            user_dict["local_admin_id"] = _fallback_local_admin(db, company_id)
        else:
            user_dict["local_admin_id"] = ObjectId(current_user_id())

    result = db.users.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)

    AuditService.log(
        action="create",
        entity_type="user",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"User {user_data.username} created as {requested_role}",
        company_id=company_id,
    )

    return jsonify(UserResponse(**user_dict).model_dump(by_alias=True)), 201


@users_bp.route("/<user_id>", methods=["GET"])
@jwt_required()
@admin_required
def get_user(user_id):
    db = get_db()
    user = db.users.find_one(_managed_query({"_id": to_object_id(user_id)}))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(UserResponse(**user).model_dump(by_alias=True)), 200


@users_bp.route("/<user_id>", methods=["PUT"])
@jwt_required()
@admin_required
def update_user(user_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        update_data = UserUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict:
        return jsonify({"error": "No fields to update"}), 400
    if "role" in update_dict:
        update_dict["role"] = normalize_role(update_dict["role"])
        if update_dict["role"] not in _allowed_roles():
            return jsonify({"error": "Role cannot be escalated"}), 403
    if "company_id" in update_dict and not is_main_admin():
        return jsonify({"error": "Only the main admin can move users between companies"}), 403

    old_user = db.users.find_one(_managed_query({"_id": to_object_id(user_id)}))
    if not old_user:
        return jsonify({"error": "User not found"}), 404

    if "company_id" in update_dict:
        company_id = to_object_id(update_dict["company_id"])
        if not _company_exists(company_id):
            return jsonify({"error": "Unknown company"}), 400
        update_dict["company_id"] = company_id

    update_dict["updated_at"] = datetime.now(timezone.utc)
    db.users.update_one({"_id": old_user["_id"]}, {"$set": update_dict})

    AuditService.log(
        action="update",
        entity_type="user",
        entity_id=str(old_user["_id"]),
        performed_by=current_user_id(),
        changes={"before": {k: str(old_user.get(k)) for k in update_dict}, "after": {k: str(v) for k, v in update_dict.items()}},
        description=f"User {old_user.get('username')} updated",
        company_id=old_user.get("company_id"),
    )

    updated = db.users.find_one({"_id": old_user["_id"]})
    return jsonify(UserResponse(**updated).model_dump(by_alias=True)), 200


@users_bp.route("/<user_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_user(user_id):
    db = get_db()
    if user_id == current_user_id():
        return jsonify({"error": "Cannot delete yourself"}), 400

    user = db.users.find_one(_managed_query({"_id": to_object_id(user_id)}))
    if not user:
        return jsonify({"error": "User not found"}), 404

    db.users.delete_one({"_id": user["_id"]})
    if user.get("role") == CUSTOMER:
        db.affairs.delete_many({"customer_id": user["_id"], "company_id": user.get("company_id")})

    AuditService.log(
        action="delete",
        entity_type="user",
        entity_id=str(user["_id"]),
        performed_by=current_user_id(),
        description=f"User {user.get('username')} deleted",
        company_id=user.get("company_id"),
    )

    return jsonify({"message": "User deleted"}), 200


@users_bp.route("/employees", methods=["GET"])
@jwt_required()
@admin_required
def list_employees():
    db = get_db()
    query = company_scope({"role": LOCAL_EMPLOYEE, "is_active": True})
    if is_main_admin():
        company_id = to_object_id(request.args.get("company_id"))
        if company_id:
            query["company_id"] = company_id
    employees = list(db.users.find(query).sort("full_name", 1))
    return jsonify([UserResponse(**e).model_dump(by_alias=True) for e in employees]), 200
