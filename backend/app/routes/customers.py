from datetime import datetime, timezone

from bcrypt import gensalt, hashpw
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.models.user import UserCreate, UserResponse
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    company_scope,
    current_company_id,
    current_user_id,
    is_customer,
    local_admin_required,
    to_object_id,
)

customers_bp = Blueprint("customers", __name__, url_prefix="/api/customers")


def _customer_query(extra=None):
    query = company_scope(extra)
    query["role"] = CUSTOMER
    return query


@customers_bp.route("/", methods=["GET"])
@jwt_required()
@local_admin_required
def list_customers():
    db = get_db()
    customers = list(db.users.find(_customer_query()).sort("full_name", 1))

    result = []
    for customer in customers:
        affair_count = db.affairs.count_documents(
            {"customer_id": customer["_id"], "company_id": customer.get("company_id")}
        )
        payload = UserResponse(**customer).model_dump(by_alias=True)
        payload["affair_count"] = affair_count
        result.append(payload)

    return jsonify(result), 200


@customers_bp.route("/<customer_id>", methods=["GET"])
@jwt_required()
def get_customer(customer_id):
    db = get_db()
    identity = get_jwt_identity()

    if is_customer():
        if identity != customer_id:
            return jsonify({"error": "Forbidden"}), 403
        customer = db.users.find_one({"_id": to_object_id(customer_id), "role": CUSTOMER})
    else:
        customer = db.users.find_one(_customer_query({"_id": to_object_id(customer_id)}))

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    affairs = list(
        db.affairs.find({"customer_id": customer["_id"], "company_id": customer.get("company_id")})
    )
    affair_ids = [a["_id"] for a in affairs]

    task_stats = {}
    if affair_ids:
        task_stats = {
            "total": db.tasks.count_documents({"affair_id": {"$in": affair_ids}}),
            "open": db.tasks.count_documents({"affair_id": {"$in": affair_ids}, "status": {"$in": ["pending", "in_progress"]}}),
            "completed": db.tasks.count_documents({"affair_id": {"$in": affair_ids}, "status": "completed"}),
        }

    payload = UserResponse(**customer).model_dump(by_alias=True)
    payload["affair_count"] = len(affairs)
    payload["task_stats"] = task_stats
    return jsonify(payload), 200


@customers_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_customer():
    db = get_db()
    data = request.get_json(silent=True) or {}
    data["role"] = CUSTOMER
    try:
        user_data = UserCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if db.users.find_one({"$or": [{"username": user_data.username}, {"email": str(user_data.email)}]}):
        return jsonify({"error": "Username or email already exists"}), 409

    now = datetime.now(timezone.utc)
    user_dict = user_data.model_dump(by_alias=True)
    user_dict["role"] = CUSTOMER
    user_dict["company_id"] = current_company_id()
    user_dict["created_by"] = ObjectId(current_user_id())
    # Their requests, activities and documents are routed to this admin.
    user_dict["local_admin_id"] = ObjectId(current_user_id())
    user_dict["password"] = hashpw(user_dict["password"].encode("utf-8"), gensalt()).decode("utf-8")
    user_dict["created_at"] = now
    user_dict["updated_at"] = now

    result = db.users.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)

    AuditService.log(
        action="create",
        entity_type="customer",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"Customer {user_data.username} created",
    )

    return jsonify(UserResponse(**user_dict).model_dump(by_alias=True)), 201


@customers_bp.route("/bulk", methods=["POST"])
@jwt_required()
@local_admin_required
def bulk_create_customers():
    db = get_db()
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array of customers"}), 400
    if len(data) > 500:
        return jsonify({"error": "Maximum 500 customers per bulk import"}), 400

    results = {"created": 0, "skipped": [], "errors": []}
    now = datetime.now(timezone.utc)
    company_id = current_company_id()
    admin_id = ObjectId(current_user_id())

    for index, item in enumerate(data):
        try:
            username = (item.get("username") or "").strip()
            email = (item.get("email") or "").strip()
            full_name = (item.get("full_name") or "").strip()
            password = item.get("password") or "customer123"
            phone = (item.get("phone") or "").strip()
            cin = (item.get("cin") or "").strip().upper()

            if not username or not email or not full_name:
                results["errors"].append({"row": index, "reason": "Missing required fields (username, email, full_name)", "data": item})
                continue

            if db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
                results["skipped"].append({"row": index, "reason": "Username or email already exists", "username": username})
                continue

            inserted = db.users.insert_one(
                {
                    "username": username,
                    "email": email,
                    "password": hashpw(password.encode("utf-8"), gensalt()).decode("utf-8"),
                    "role": CUSTOMER,
                    "full_name": full_name,
                    "phone": phone or None,
                    "cin": cin or None,
                    "is_active": True,
                    "company_id": company_id,
                    "created_by": admin_id,
                    "local_admin_id": admin_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            AuditService.log(
                action="create",
                entity_type="customer",
                entity_id=str(inserted.inserted_id),
                performed_by=current_user_id(),
                description=f"Customer {username} created (bulk import)",
            )
            results["created"] += 1

        except Exception as exc:
            results["errors"].append({"row": index, "reason": str(exc), "data": item})

    return jsonify(results), 201


@customers_bp.route("/<customer_id>", methods=["PUT"])
@jwt_required()
@local_admin_required
def update_customer(customer_id):
    db = get_db()
    data = request.get_json(silent=True) or {}

    customer = db.users.find_one(_customer_query({"_id": to_object_id(customer_id)}))
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    update_dict = {}
    for field in ("full_name", "email", "phone", "is_active", "cin", "photo_id"):
        if field in data:
            update_dict[field] = data[field]

    if not update_dict:
        return jsonify({"error": "No fields to update"}), 400

    update_dict["updated_at"] = datetime.now(timezone.utc)
    db.users.update_one({"_id": customer["_id"]}, {"$set": update_dict})

    AuditService.log(
        action="update",
        entity_type="customer",
        entity_id=str(customer["_id"]),
        performed_by=current_user_id(),
        description=f"Customer {customer.get('username')} updated",
    )

    updated = db.users.find_one({"_id": customer["_id"]})
    return jsonify(UserResponse(**updated).model_dump(by_alias=True)), 200


@customers_bp.route("/<customer_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_customer(customer_id):
    db = get_db()
    customer = db.users.find_one(_customer_query({"_id": to_object_id(customer_id)}))
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    affairs = list(db.affairs.find({"customer_id": customer["_id"]}))
    for affair in affairs:
        AuditService.log(
            action="delete",
            entity_type="affair",
            entity_id=str(affair["_id"]),
            performed_by=current_user_id(),
            description=f"Affair '{affair.get('name')}' deleted (customer cascade)",
        )
    db.affairs.delete_many({"customer_id": customer["_id"]})
    db.documents.delete_many({"customer_id": customer["_id"]})
    db.users.delete_one({"_id": customer["_id"]})

    AuditService.log(
        action="delete",
        entity_type="customer",
        entity_id=str(customer["_id"]),
        performed_by=current_user_id(),
        description=f"Customer {customer.get('username')} deleted",
    )

    return jsonify({"message": "Customer deleted"}), 200
