from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.models.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.audit_service import AuditService
from app.socketio_server import notify_badge_update, notify_user
from app.tenancy import (
    company_scope,
    current_company_id,
    current_user_id,
    is_customer,
    is_local_employee,
    local_admin_required,
    local_staff_required,
    to_object_id,
)
from app.utils.localize import localize_task

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _notify_local_admins(db, task, task_id):
    """An employee's new task waits for a local admin to validate it."""
    now = datetime.now(timezone.utc)
    creator = db.users.find_one({"_id": to_object_id(current_user_id())}) or {}
    creator_name = creator.get("full_name") or creator.get("username") or "An employee"
    message = f"{creator_name} added the task '{task['title']}' and it needs your validation."

    for admin in db.users.find({"company_id": task["company_id"], "role": "local_admin"}):
        notif_id = db.notifications.insert_one(
            {
                "user_id": admin["_id"],
                "company_id": task["company_id"],
                "type": "task_validation",
                "title": "Task needs validation",
                "message": message,
                "task_id": task_id,
                "read": False,
                "created_at": now,
            }
        ).inserted_id

        notify_user(
            str(admin["_id"]),
            {
                "_id": str(notif_id),
                "type": "task_validation",
                "title": "Task needs validation",
                "message": message,
                "task_id": str(task_id),
                "read": False,
                "created_at": now.isoformat(),
            },
        )
        notify_badge_update(str(admin["_id"]))


@tasks_bp.route("/", methods=["POST"])
@jwt_required()
@local_staff_required
def create_task():
    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        task_data = TaskCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    task_dict = task_data.model_dump()
    task_dict["company_id"] = current_company_id()
    task_dict["created_by"] = ObjectId(current_user_id())
    task_dict["created_at"] = datetime.now(timezone.utc)
    task_dict["updated_at"] = datetime.now(timezone.utc)

    assigned_to = data.get("assigned_to")
    if assigned_to:
        employee = db.users.find_one(
            company_scope({"_id": to_object_id(assigned_to), "role": "local_employee"})
        )
        if not employee:
            return jsonify({"error": "Assigned user must be an employee of your company"}), 400
        task_dict["assigned_to"] = employee["_id"]

    result = db.tasks.insert_one(task_dict)
    task_dict["_id"] = str(result.inserted_id)

    AuditService.log(
        action="create",
        entity_type="task",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"Task '{task_data.title}' created",
    )

    # A local admin validates the tasks their employees add.
    if is_local_employee():
        _notify_local_admins(db, task_dict, result.inserted_id)

    return jsonify(TaskResponse(**localize_task(task_dict)).model_dump(by_alias=True)), 201


@tasks_bp.route("/", methods=["GET"])
@jwt_required()
@local_staff_required
def list_tasks():
    db = get_db()
    query = company_scope()

    status = request.args.get("status")
    if status:
        query["status"] = status

    sort_field = request.args.get("sort", "created_at")
    sort_order = -1 if request.args.get("order", "desc") == "desc" else 1

    tasks = list(db.tasks.find(query).sort(sort_field, sort_order))
    return jsonify([TaskResponse(**localize_task(t)).model_dump(by_alias=True) for t in tasks]), 200


@tasks_bp.route("/<task_id>", methods=["GET"])
@jwt_required()
@local_staff_required
def get_task(task_id):
    db = get_db()
    task = db.tasks.find_one(company_scope({"_id": to_object_id(task_id)}))
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(TaskResponse(**localize_task(task)).model_dump(by_alias=True)), 200


@tasks_bp.route("/<task_id>", methods=["PUT"])
@jwt_required()
@local_staff_required
def update_task(task_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    try:
        update_data = TaskUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict:
        return jsonify({"error": "No fields to update"}), 400

    old = db.tasks.find_one(company_scope({"_id": to_object_id(task_id)}))
    if not old:
        return jsonify({"error": "Task not found"}), 404

    update_dict["updated_at"] = datetime.now(timezone.utc)
    db.tasks.update_one({"_id": old["_id"]}, {"$set": update_dict})

    AuditService.log(
        action="update",
        entity_type="task",
        entity_id=str(old["_id"]),
        performed_by=current_user_id(),
        changes={"before": {k: str(old.get(k)) for k in update_dict}, "after": {k: str(v) for k, v in update_dict.items()}},
        description=f"Task '{old.get('title')}' updated",
    )

    updated = db.tasks.find_one({"_id": old["_id"]})
    return jsonify(TaskResponse(**localize_task(updated)).model_dump(by_alias=True)), 200


@tasks_bp.route("/<task_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_task(task_id):
    db = get_db()
    task = db.tasks.find_one(company_scope({"_id": to_object_id(task_id)}))
    if not task:
        return jsonify({"error": "Task not found"}), 404

    db.tasks.delete_one({"_id": task["_id"]})

    AuditService.log(
        action="delete",
        entity_type="task",
        entity_id=str(task["_id"]),
        performed_by=current_user_id(),
        description=f"Task '{task.get('title')}' deleted",
    )

    return jsonify({"message": "Task deleted"}), 200
