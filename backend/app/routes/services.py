from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.models.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.audit_service import AuditService
from app.tenancy import (
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    MAIN_ADMIN,
    company_scope,
    current_company_id,
    current_user_id,
    is_main_admin,
    local_admin_required,
    local_staff_required,
    role_required,
    to_object_id,
)
from app.utils.localize import localize_service

services_bp = Blueprint("services", __name__, url_prefix="/api/services")


def _update_task_assignments(service_id, task_ids, performed_by):
    """Assign/unassign tasks to/from a service, inside the caller's company."""
    db = get_db()
    company_id = current_company_id()
    old_tasks = list(db.tasks.find({"service_id": ObjectId(service_id), "company_id": company_id}, {"_id": 1}))
    old_ids = {str(t["_id"]) for t in old_tasks}
    new_ids = set(task_ids or [])

    to_add = new_ids - old_ids
    to_remove = old_ids - new_ids

    if to_add:
        tasks = list(
            db.tasks.find(
                {"_id": {"$in": [ObjectId(tid) for tid in to_add]}, "company_id": company_id}, {"title": 1}
            )
        )
        db.tasks.update_many(
            {"_id": {"$in": [ObjectId(tid) for tid in to_add]}, "company_id": company_id},
            {"$set": {"service_id": ObjectId(service_id), "updated_at": datetime.now(timezone.utc)}},
        )
        for task in tasks:
            AuditService.log(
                action="update",
                entity_type="task",
                entity_id=str(task["_id"]),
                performed_by=performed_by,
                description=f"Task '{task.get('title')}' assigned to service",
            )
    if to_remove:
        tasks = list(
            db.tasks.find(
                {"_id": {"$in": [ObjectId(tid) for tid in to_remove]}, "company_id": company_id}, {"title": 1}
            )
        )
        db.tasks.update_many(
            {"_id": {"$in": [ObjectId(tid) for tid in to_remove]}, "company_id": company_id},
            {"$unset": {"service_id": ""}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        for task in tasks:
            AuditService.log(
                action="update",
                entity_type="task",
                entity_id=str(task["_id"]),
                performed_by=performed_by,
                description=f"Task '{task.get('title')}' unassigned from service",
            )

    db.services.update_one(
        {"_id": ObjectId(service_id), "company_id": company_id},
        {"$set": {"task_ids": [ObjectId(tid) for tid in new_ids], "updated_at": datetime.now(timezone.utc)}},
    )


@services_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_service():
    db = get_db()
    data = request.get_json(silent=True) or {}
    task_ids = data.pop("task_ids", None)
    if not task_ids:
        return jsonify({"error": "At least one task must be assigned to the service"}), 400
    try:
        service_data = ServiceCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    now = datetime.now(timezone.utc)
    service_dict = service_data.model_dump()
    service_dict["task_ids"] = [ObjectId(tid) for tid in task_ids]
    service_dict["company_id"] = current_company_id()
    service_dict["created_at"] = now
    service_dict["updated_at"] = now

    result = db.services.insert_one(service_dict)
    sid = str(result.inserted_id)
    service_dict["_id"] = sid

    _update_task_assignments(sid, task_ids, current_user_id())

    AuditService.log(
        action="create",
        entity_type="service",
        entity_id=sid,
        performed_by=current_user_id(),
        description=f"Service '{service_data.name}' created",
    )

    return jsonify(ServiceResponse(**localize_service(service_dict)).model_dump(by_alias=True)), 201


@services_bp.route("/", methods=["GET"])
@jwt_required()
@role_required(MAIN_ADMIN, LOCAL_ADMIN, LOCAL_EMPLOYEE)
def list_services():
    db = get_db()
    query = company_scope()
    if is_main_admin():
        # The platform admin reads one company's catalogue at a time.
        company_id = to_object_id(request.args.get("company_id"))
        if company_id is None:
            return jsonify({"error": "company_id is required"}), 400
        query["company_id"] = company_id
    services = list(db.services.find(query).sort("name", 1))
    return jsonify([ServiceResponse(**localize_service(s)).model_dump(by_alias=True) for s in services]), 200


@services_bp.route("/<service_id>", methods=["GET"])
@jwt_required()
@local_staff_required
def get_service(service_id):
    db = get_db()
    service = db.services.find_one(company_scope({"_id": to_object_id(service_id)}))
    if not service:
        return jsonify({"error": "Service not found"}), 404
    return jsonify(ServiceResponse(**localize_service(service)).model_dump(by_alias=True)), 200


@services_bp.route("/<service_id>", methods=["PUT"])
@jwt_required()
@local_admin_required
def update_service(service_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    task_ids = data.pop("task_ids", None)
    if task_ids is not None and len(task_ids) < 1:
        return jsonify({"error": "At least one task must be assigned to the service"}), 400
    try:
        update_data = ServiceUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict and task_ids is None:
        return jsonify({"error": "No fields to update"}), 400

    old = db.services.find_one(company_scope({"_id": to_object_id(service_id)}))
    if not old:
        return jsonify({"error": "Service not found"}), 404

    update_dict["updated_at"] = datetime.now(timezone.utc)
    if update_dict:
        db.services.update_one({"_id": old["_id"]}, {"$set": update_dict})

    if task_ids is not None:
        _update_task_assignments(str(old["_id"]), task_ids, current_user_id())

    AuditService.log(
        action="update",
        entity_type="service",
        entity_id=str(old["_id"]),
        performed_by=current_user_id(),
        changes={"before": {k: str(old.get(k)) for k in update_dict}, "after": {k: str(v) for k, v in update_dict.items()}},
        description=f"Service '{old.get('name')}' updated",
    )

    updated = db.services.find_one({"_id": old["_id"]})
    return jsonify(ServiceResponse(**localize_service(updated)).model_dump(by_alias=True)), 200


@services_bp.route("/<service_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_service(service_id):
    db = get_db()
    service = db.services.find_one(company_scope({"_id": to_object_id(service_id)}))
    if not service:
        return jsonify({"error": "Service not found"}), 404

    db.services.delete_one({"_id": service["_id"]})

    AuditService.log(
        action="delete",
        entity_type="service",
        entity_id=str(service["_id"]),
        performed_by=current_user_id(),
        description=f"Service '{service.get('name')}' deleted",
    )

    return jsonify({"message": "Service deleted"}), 200
