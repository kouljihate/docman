from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.models.affair import AffairCreate, AffairResponse, AffairUpdate
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    company_scope,
    current_user_id,
    is_customer,
    local_admin_required,
    role_required,
    to_object_id,
)

affairs_bp = Blueprint("affairs", __name__, url_prefix="/api/affairs")


@affairs_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_affair():
    db = get_db()
    try:
        affair_data = AffairCreate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    customer = db.users.find_one(
        company_scope({"_id": to_object_id(affair_data.customer_id), "role": CUSTOMER})
    )
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    affair_dict = affair_data.model_dump(by_alias=True)
    affair_dict["customer_id"] = customer["_id"]
    affair_dict["company_id"] = customer.get("company_id")
    affair_dict["created_at"] = datetime.now(timezone.utc)
    affair_dict["updated_at"] = datetime.now(timezone.utc)

    result = db.affairs.insert_one(affair_dict)
    affair_dict["_id"] = str(result.inserted_id)

    AuditService.log(
        action="create",
        entity_type="affair",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"Affair '{affair_data.name}' created for customer",
    )

    return jsonify(AffairResponse(**affair_dict).model_dump(by_alias=True)), 201


@affairs_bp.route("/", methods=["GET"])
@jwt_required()
@role_required("main_admin", "local_admin", "local_employee", "customer")
def list_affairs():
    db = get_db()
    identity = get_jwt_identity()

    customer_id = request.args.get("customer_id")
    query = company_scope()
    if customer_id:
        query["customer_id"] = to_object_id(customer_id)
    if is_customer():
        query["customer_id"] = to_object_id(identity)

    pipeline = [
        {"$match": query},
        {"$sort": {"name": 1}},
        {"$lookup": {"from": "users", "localField": "customer_id", "foreignField": "_id", "as": "customer"}},
        {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"customer_name": "$customer.full_name"}},
        {"$project": {"customer": 0}},
    ]

    affairs = list(db.affairs.aggregate(pipeline))
    return jsonify([AffairResponse(**a).model_dump(by_alias=True) for a in affairs]), 200


@affairs_bp.route("/<affair_id>", methods=["GET"])
@jwt_required()
@role_required("main_admin", "local_admin", "local_employee", "customer")
def get_affair(affair_id):
    db = get_db()
    query = company_scope({"_id": to_object_id(affair_id)})
    if is_customer():
        query["customer_id"] = to_object_id(get_jwt_identity())

    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "users", "localField": "customer_id", "foreignField": "_id", "as": "customer"}},
        {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"customer_name": "$customer.full_name"}},
        {"$project": {"customer": 0}},
    ]
    affairs = list(db.affairs.aggregate(pipeline))
    if not affairs:
        return jsonify({"error": "Affair not found"}), 404
    return jsonify(AffairResponse(**affairs[0]).model_dump(by_alias=True)), 200


@affairs_bp.route("/<affair_id>", methods=["PUT"])
@jwt_required()
@local_admin_required
def update_affair(affair_id):
    db = get_db()
    try:
        update_data = AffairUpdate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict:
        return jsonify({"error": "No fields to update"}), 400

    old = db.affairs.find_one(company_scope({"_id": to_object_id(affair_id)}))
    if not old:
        return jsonify({"error": "Affair not found"}), 404

    update_dict["updated_at"] = datetime.now(timezone.utc)
    db.affairs.update_one({"_id": old["_id"]}, {"$set": update_dict})

    AuditService.log(
        action="update",
        entity_type="affair",
        entity_id=str(old["_id"]),
        performed_by=current_user_id(),
        changes={"before": {k: str(old.get(k)) for k in update_dict}, "after": {k: str(v) for k, v in update_dict.items()}},
        description=f"Affair '{old.get('name')}' updated",
    )

    updated = db.affairs.find_one({"_id": old["_id"]})
    return jsonify(AffairResponse(**updated).model_dump(by_alias=True)), 200


@affairs_bp.route("/<affair_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_affair(affair_id):
    db = get_db()
    affair = db.affairs.find_one(company_scope({"_id": to_object_id(affair_id)}))
    if not affair:
        return jsonify({"error": "Affair not found"}), 404

    db.affairs.delete_one({"_id": affair["_id"]})

    AuditService.log(
        action="delete",
        entity_type="affair",
        entity_id=str(affair["_id"]),
        performed_by=current_user_id(),
        description=f"Affair '{affair.get('name')}' deleted",
    )

    return jsonify({"message": "Affair deleted"}), 200
