from datetime import datetime, timezone

from bcrypt import checkpw, gensalt, hashpw
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from app.database import get_db
from app.models.user import UserCreate, UserLogin, UserResponse
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    MAIN_ADMIN,
    normalize_role,
    to_object_id,
)
from config import settings

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Public sign-up.

    The very first account bootstraps the platform ``main_admin``. Everyone
    else joins an existing company as a customer; privileged roles are only
    ever granted by an administrator.
    """
    data = request.get_json(silent=True) or {}
    db = get_db()

    # A role can never be self-assigned.
    data = {k: v for k, v in data.items() if k != "role"}

    is_bootstrap = db.users.count_documents({}) == 0
    company_doc = None
    if is_bootstrap:
        role = MAIN_ADMIN
        company_id = None
    else:
        company_id = to_object_id(data.pop("company_id", None))
        if company_id is None:
            return jsonify({"error": "Select a company to register with"}), 400
        company_doc = db.companies.find_one({"_id": company_id, "is_active": True})
        if not company_doc:
            return jsonify({"error": "Company not found or inactive"}), 400
        role = CUSTOMER

    try:
        user_data = UserCreate(role=role, **data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if db.users.find_one({"$or": [{"username": user_data.username}, {"email": str(user_data.email)}]}):
        return jsonify({"error": "Username or email already exists"}), 409

    now = datetime.now(timezone.utc)
    user_dict = user_data.model_dump(by_alias=True)
    user_dict["role"] = role
    user_dict["company_id"] = company_id
    user_dict["password"] = hashpw(user_dict["password"].encode("utf-8"), gensalt()).decode("utf-8")
    user_dict["created_at"] = now
    user_dict["updated_at"] = now

    if company_doc is not None:
        # Requests from this customer go to their own local admin.
        local_admin = db.users.find_one(
            {"company_id": company_id, "role": LOCAL_ADMIN, "is_active": True}
        )
        user_dict["local_admin_id"] = local_admin["_id"] if local_admin else None

    result = db.users.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)

    AuditService.log(
        action="create",
        entity_type="user",
        entity_id=str(result.inserted_id),
        performed_by=str(result.inserted_id),
        description=f"User {user_data.username} registered as {role}",
        company_id=company_id,
    )

    return jsonify(UserResponse(**user_dict).model_dump(by_alias=True)), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    try:
        login_data = UserLogin(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    user = db.users.find_one({"username": login_data.username})

    if not user or not checkpw(login_data.password.encode("utf-8"), user["password"].encode("utf-8")):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.get("is_active", True):
        return jsonify({"error": "Account is disabled"}), 403

    role = normalize_role(user.get("role"))
    company_id = user.get("company_id")

    access_token = create_access_token(
        identity=str(user["_id"]),
        additional_claims={
            "role": role,
            "username": user["username"],
            "company_id": str(company_id) if company_id else "",
        },
    )

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"

    AuditService.log(
        action="login",
        entity_type="auth",
        entity_id=str(user["_id"]),
        performed_by=str(user["_id"]),
        description=f"User '{user.get('username')}' logged in from IP {ip}",
        company_id=company_id,
    )

    # The token is only delivered as an HttpOnly cookie so page scripts can
    # never read it; the JSON body carries the user profile alone.
    user_copy = dict(user)
    user_copy["role"] = role
    resp = jsonify({"user": UserResponse(**user_copy).model_dump(by_alias=True)})
    resp.set_cookie(
        "access_token",
        access_token,
        max_age=settings.jwt_access_token_expires,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Lax",
        path="/",
    )
    return resp, 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    user_id = get_jwt_identity()
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})

    AuditService.log(
        action="logout",
        entity_type="auth",
        entity_id=user_id,
        performed_by=user_id,
        description=f"User '{user.get('username') if user else 'Unknown'}' logged out",
        company_id=user.get("company_id") if user else None,
    )

    resp = jsonify({"ok": True})
    resp.delete_cookie("access_token", path="/", samesite="Lax")
    return resp, 200


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = dict(user)
    data["role"] = normalize_role(data.get("role"))
    payload = UserResponse(**data).model_dump(by_alias=True)
    company = db.companies.find_one({"_id": user["company_id"]}) if user.get("company_id") else None
    payload["company"] = (
        {"_id": str(company["_id"]), "company_name": company.get("company_name")} if company else None
    )
    return jsonify(payload), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Current and new password are required"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not checkpw(current_password.encode("utf-8"), user["password"].encode("utf-8")):
        return jsonify({"error": "Current password is incorrect"}), 401

    hashed = hashpw(new_password.encode("utf-8"), gensalt()).decode("utf-8")
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hashed, "updated_at": datetime.now(timezone.utc)}},
    )

    AuditService.log(
        action="update",
        entity_type="user",
        entity_id=user_id,
        performed_by=user_id,
        description="Password changed",
        company_id=user.get("company_id"),
    )

    return jsonify({"ok": True, "message": "Password changed successfully"}), 200
