from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import get_db
from app.models.payment import PaymentCreate, PaymentResponse, PaymentUpdate
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    company_scope,
    current_company_id,
    current_user_id,
    local_admin_required,
    to_object_id,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

UPDATE_FIELDS = ("label", "amount", "currency", "due_date", "status", "method", "notes")


def _aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _serialize(payment, customers):
    due_date = _aware(payment.get("due_date"))
    is_overdue = (
        payment.get("status") == "pending"
        and due_date is not None
        and due_date < datetime.now(timezone.utc)
    )
    doc = dict(payment)
    doc["due_date"] = due_date
    doc["is_overdue"] = is_overdue
    doc["display_status"] = "overdue" if is_overdue else payment.get("status", "pending")

    customer = customers.get(payment.get("customer_id"))
    if customer:
        doc["customer_name"] = customer.get("full_name") or customer.get("username")
        doc["customer_username"] = customer.get("username")

    return PaymentResponse(**doc).model_dump(by_alias=True)


def _customers_map(customer_ids):
    ids = [cid for cid in customer_ids if isinstance(cid, ObjectId)]
    if not ids:
        return {}
    return {
        user["_id"]: user
        for user in get_db().users.find({"_id": {"$in": ids}, "role": CUSTOMER})
    }


def _find_customer(customer_id):
    """A customer of the caller's company, or None."""
    return get_db().users.find_one(
        {
            "_id": to_object_id(customer_id),
            "role": CUSTOMER,
            "company_id": current_company_id(),
        }
    )


@payments_bp.route("/", methods=["GET"])
@jwt_required()
@local_admin_required
def list_payments():
    db = get_db()
    query = company_scope()

    customer_id = request.args.get("customer_id")
    if customer_id:
        query["customer_id"] = to_object_id(customer_id)

    status = request.args.get("status")
    if status in ("pending", "paid", "cancelled"):
        query["status"] = status

    payments = list(db.payments.find(query).sort("due_date", 1))
    customers = _customers_map(payment.get("customer_id") for payment in payments)
    return jsonify([_serialize(payment, customers) for payment in payments]), 200


@payments_bp.route("/<payment_id>", methods=["GET"])
@jwt_required()
@local_admin_required
def get_payment(payment_id):
    payment = get_db().payments.find_one(company_scope({"_id": to_object_id(payment_id)}))
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
    return jsonify(_serialize(payment, _customers_map([payment.get("customer_id")]))), 200


@payments_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_payment():
    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        payment_data = PaymentCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    customer = _find_customer(payment_data.customer_id)
    if not customer:
        return jsonify({"error": "Customer not found in your company"}), 400

    now = datetime.now(timezone.utc)
    payment_dict = payment_data.model_dump()
    payment_dict["due_date"] = _aware(payment_dict["due_date"])
    payment_dict["customer_id"] = customer["_id"]
    payment_dict["company_id"] = current_company_id()
    payment_dict["created_by"] = ObjectId(current_user_id())
    payment_dict["paid_at"] = now if payment_dict["status"] == "paid" else None
    payment_dict["created_at"] = now
    payment_dict["updated_at"] = now

    result = db.payments.insert_one(payment_dict)
    payment_dict["_id"] = result.inserted_id

    AuditService.log(
        action="create",
        entity_type="payment",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"Payment of {payment_data.amount} {payment_data.currency} for {customer.get('username')} created",
    )

    return jsonify(_serialize(payment_dict, {customer["_id"]: customer})), 201


@payments_bp.route("/<payment_id>", methods=["PUT"])
@jwt_required()
@local_admin_required
def update_payment(payment_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        update_data = PaymentUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {
        k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None
    }
    if not update_dict:
        return jsonify({"error": "No fields to update"}), 400

    payment = db.payments.find_one(company_scope({"_id": to_object_id(payment_id)}))
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    customer = None
    if "customer_id" in update_dict:
        customer = _find_customer(update_dict["customer_id"])
        if not customer:
            return jsonify({"error": "Customer not found in your company"}), 400
        update_dict["customer_id"] = customer["_id"]

    now = datetime.now(timezone.utc)
    if "due_date" in update_dict:
        update_dict["due_date"] = _aware(update_dict["due_date"])
    if "status" in update_dict:
        if update_dict["status"] == "paid":
            update_dict["paid_at"] = payment.get("paid_at") or now
        else:
            update_dict["paid_at"] = None
    update_dict["updated_at"] = now

    db.payments.update_one({"_id": payment["_id"]}, {"$set": update_dict})
    updated = db.payments.find_one({"_id": payment["_id"]})
    customers = _customers_map([updated.get("customer_id")])

    AuditService.log(
        action="update",
        entity_type="payment",
        entity_id=str(payment["_id"]),
        performed_by=current_user_id(),
        description=f"Payment {payment.get('label') or payment['_id']} updated",
    )

    return jsonify(_serialize(updated, customers)), 200


@payments_bp.route("/<payment_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_payment(payment_id):
    db = get_db()
    payment = db.payments.find_one(company_scope({"_id": to_object_id(payment_id)}))
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    db.payments.delete_one({"_id": payment["_id"]})

    AuditService.log(
        action="delete",
        entity_type="payment",
        entity_id=str(payment["_id"]),
        performed_by=current_user_id(),
        description=f"Payment {payment.get('label') or payment['_id']} deleted",
    )

    return jsonify({"message": "Payment deleted"}), 200
