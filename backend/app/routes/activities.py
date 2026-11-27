from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from bson import ObjectId
from app.database import get_db
from app.services.audit_service import AuditService
from app.socketio_server import notify_user, notify_badge_update
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    company_scope,
    current_company_id,
    current_role,
    current_user_id,
    local_admin_required,
    local_staff_required,
    role_required,
    to_object_id,
)

activities_bp = Blueprint("activities", __name__, url_prefix="/api/activities")


def _serialize_activity(activity):
    """JSON-ready copy of an activity document."""
    data = {}
    for key, value in activity.items():
        if isinstance(value, ObjectId):
            data[key] = str(value)
        elif isinstance(value, list):
            data[key] = [str(item) if isinstance(item, ObjectId) else item for item in value]
        else:
            data[key] = value
    return data


@activities_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_activity():
    db = get_db()
    data = request.get_json()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    assigned_to = data.get("assigned_to", "").strip()
    customer_id = data.get("customer_id", "").strip()
    task_ids = data.get("task_ids", [])

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not assigned_to:
        return jsonify({"error": "Assigned employee is required"}), 400
    if not db.users.find_one(
        company_scope({"_id": to_object_id(assigned_to), "role": {"$in": [LOCAL_EMPLOYEE, LOCAL_ADMIN]}})
    ):
        return jsonify({"error": "Assigned user must be an employee or local manager of your company"}), 400
    if not customer_id:
        return jsonify({"error": "Customer is required"}), 400
    if not db.users.find_one(company_scope({"_id": to_object_id(customer_id), "role": CUSTOMER})):
        return jsonify({"error": "Customer not found"}), 400

    admin_id = get_jwt_identity()
    now = datetime.now(timezone.utc)

    notes = data.get("notes", "").strip()

    affair_id = data.get("affair_id", "").strip() if data.get("affair_id") else None
    if affair_id and not db.affairs.find_one(company_scope({"_id": to_object_id(affair_id)})):
        return jsonify({"error": "Affair not found"}), 404

    activity_dict = {
        "title": title,
        "description": description or None,
        "assigned_to": ObjectId(assigned_to),
        "assigned_by": ObjectId(admin_id),
        "customer_id": ObjectId(customer_id),
        "affair_id": ObjectId(affair_id) if affair_id else None,
        "task_ids": [ObjectId(tid) for tid in task_ids],
        # Created directly for an employee, so it is already assigned.
        "status": "assigned",
        "notes": notes or None,
        "company_id": current_company_id(),
        "created_at": now,
        "updated_at": now,
    }
    result = db.activities.insert_one(activity_dict)
    activity_dict["_id"] = str(result.inserted_id)

    notif_id = db.notifications.insert_one({
        "user_id": ObjectId(assigned_to),
        "company_id": current_company_id(),
        "type": "activity_assigned",
        "title": "New Activity Assigned",
        "message": f"You have been assigned a new activity: {title}",
        "activity_id": result.inserted_id,
        "read": False,
        "created_at": now,
    }).inserted_id

    AuditService.log(
        action="create",
        entity_type="notification",
        entity_id=str(notif_id),
        performed_by=admin_id,
        description=f"Activity assigned notification sent to user {assigned_to}",
    )

    notify_user(assigned_to, {
        "_id": str(notif_id),
        "type": "activity_assigned",
        "title": "New Activity Assigned",
        "message": f"You have been assigned a new activity: {title}",
        "activity_id": str(result.inserted_id),
        "read": False,
        "created_at": now.isoformat(),
    })
    notify_badge_update(assigned_to)

    AuditService.log(
        action="create",
        entity_type="activity",
        entity_id=str(result.inserted_id),
        performed_by=admin_id,
        description=f"Activity '{title}' created for employee",
    )

    activity_dict["assigned_to"] = str(activity_dict["assigned_to"])
    activity_dict["assigned_by"] = str(activity_dict["assigned_by"])
    activity_dict["customer_id"] = str(activity_dict["customer_id"])
    activity_dict["affair_id"] = str(activity_dict["affair_id"]) if activity_dict["affair_id"] else None
    activity_dict["task_ids"] = [str(tid) for tid in activity_dict["task_ids"]]

    tasks_data = list(db.tasks.find({"_id": {"$in": [ObjectId(tid) for tid in task_ids]}}, {"title": 1}))
    activity_dict["task_names"] = [t["title"] for t in tasks_data]

    customer = db.users.find_one({"_id": ObjectId(customer_id)}, {"full_name": 1})
    activity_dict["customer_name"] = customer["full_name"] if customer else None

    return jsonify(activity_dict), 201


@activities_bp.route("/", methods=["GET"])
@jwt_required()
def list_activities():
    db = get_db()
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")

    query = company_scope()
    assigned_to_filter = request.args.get("assigned_to")
    if assigned_to_filter:
        query["assigned_to"] = ObjectId(assigned_to_filter)
    elif role == LOCAL_EMPLOYEE:
        query["assigned_to"] = ObjectId(identity)
    elif role == CUSTOMER:
        query["customer_id"] = ObjectId(identity)

    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "assigned_user",
            }
        },
        {"$unwind": {"path": "$assigned_user", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_by",
                "foreignField": "_id",
                "as": "assigned_by_user",
            }
        },
        {"$unwind": {"path": "$assigned_by_user", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "users",
                "localField": "customer_id",
                "foreignField": "_id",
                "as": "customer_user",
            }
        },
        {"$unwind": {"path": "$customer_user", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "tasks",
                "localField": "task_ids",
                "foreignField": "_id",
                "as": "tasks",
            }
        },
        {
            "$lookup": {
                "from": "affairs",
                "localField": "affair_id",
                "foreignField": "_id",
                "as": "affair",
            }
        },
        {"$unwind": {"path": "$affair", "preserveNullAndEmptyArrays": True}},
        {
            "$addFields": {
                "assigned_to_name": "$assigned_user.full_name",
                "assigned_by_name": "$assigned_by_user.full_name",
                "customer_name": "$customer_user.full_name",
                "affair_name": "$affair.name",
                "affair_reference": "$affair.reference",
                "task_names": {"$map": {"input": "$tasks", "as": "t", "in": "$$t.title"}},
            }
        },
        {"$project": {"assigned_user": 0, "assigned_by_user": 0, "customer_user": 0, "tasks": 0, "affair": 0}},
    ]

    activities = [_serialize_activity(a) for a in db.activities.aggregate(pipeline)]
    return jsonify(activities), 200


@activities_bp.route("/<activity_id>", methods=["GET"])
@jwt_required()
def get_activity(activity_id):
    db = get_db()
    match = company_scope({"_id": to_object_id(activity_id)})
    if current_role() == CUSTOMER:
        match["customer_id"] = ObjectId(get_jwt_identity())
    pipeline = [
        {"$match": match},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "assigned_user",
            }
        },
        {"$unwind": {"path": "$assigned_user", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_by",
                "foreignField": "_id",
                "as": "assigned_by_user",
            }
        },
        {"$unwind": {"path": "$assigned_by_user", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "tasks",
                "localField": "task_ids",
                "foreignField": "_id",
                "as": "tasks",
            }
        },
        {
            "$addFields": {
                "assigned_to_name": "$assigned_user.full_name",
                "assigned_by_name": "$assigned_by_user.full_name",
                "task_names": {"$map": {"input": "$tasks", "as": "t", "in": "$$t.title"}},
            }
        },
        {"$project": {"assigned_user": 0, "assigned_by_user": 0, "tasks": 0}},
    ]
    activities = list(db.activities.aggregate(pipeline))
    if not activities:
        return jsonify({"error": "Activity not found"}), 404
    return jsonify(_serialize_activity(activities[0])), 200


@activities_bp.route("/<activity_id>/assign", methods=["PUT"])
@jwt_required()
@local_admin_required
def assign_activity(activity_id):
    """Hand an activity to an employee, or take it back to the pending pool."""
    db = get_db()
    data = request.get_json(silent=True) or {}
    assigned_to = (data.get("assigned_to") or "").strip()

    activity = db.activities.find_one(company_scope({"_id": to_object_id(activity_id)}))
    if not activity:
        return jsonify({"error": "Activity not found"}), 404
    if activity.get("status") in ("completed", "cancelled"):
        return jsonify({"error": "This activity is closed"}), 400

    now = datetime.now(timezone.utc)
    update = {"updated_at": now}

    if assigned_to:
        employee = db.users.find_one(
            company_scope(
                {
                    "_id": to_object_id(assigned_to),
                    "role": {"$in": [LOCAL_EMPLOYEE, LOCAL_ADMIN]},
                    "is_active": True,
                }
            )
        )
        if not employee:
            return jsonify({"error": "Assigned user must be an employee of your company"}), 400

        update["assigned_to"] = employee["_id"]
        update["assigned_by"] = ObjectId(current_user_id())
        if activity.get("status") in ("pending", "assigned"):
            update["status"] = "assigned"
        db.activities.update_one({"_id": activity["_id"]}, {"$set": update})

        notif_id = db.notifications.insert_one(
            {
                "user_id": employee["_id"],
                "company_id": current_company_id(),
                "type": "activity_assigned",
                "title": "New Activity Assigned",
                "message": f"You have been assigned a new activity: {activity.get('title')}",
                "activity_id": activity["_id"],
                "affair_id": activity.get("affair_id"),
                "read": False,
                "created_at": now,
            }
        ).inserted_id
        notify_user(
            str(employee["_id"]),
            {
                "_id": str(notif_id),
                "type": "activity_assigned",
                "title": "New Activity Assigned",
                "message": f"You have been assigned a new activity: {activity.get('title')}",
                "activity_id": activity_id,
                "read": False,
                "created_at": now.isoformat(),
            },
        )
        notify_badge_update(str(employee["_id"]))

        AuditService.log(
            action="update",
            entity_type="activity",
            entity_id=activity_id,
            performed_by=current_user_id(),
            description=f"Activity '{activity.get('title')}' assigned to {employee.get('full_name')}",
        )
    else:
        update["assigned_to"] = None
        if activity.get("status") == "assigned":
            update["status"] = "pending"
        db.activities.update_one({"_id": activity["_id"]}, {"$set": update})

        AuditService.log(
            action="update",
            entity_type="activity",
            entity_id=activity_id,
            performed_by=current_user_id(),
            description=f"Activity '{activity.get('title')}' unassigned",
        )

    updated = db.activities.find_one({"_id": activity["_id"]})
    return jsonify(_serialize_activity(updated)), 200


@activities_bp.route("/<activity_id>/status", methods=["PUT"])
@jwt_required()
def update_activity_status(activity_id):
    db = get_db()
    identity = get_jwt_identity()
    claims = get_jwt()
    data = request.get_json()
    new_status = data.get("status", "").strip()

    if new_status not in ("in_progress", "completed", "cancelled"):
        return jsonify({"error": "Invalid status"}), 400

    activity = db.activities.find_one(company_scope({"_id": to_object_id(activity_id)}))
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    current = activity.get("status")
    role = current_role()

    if role != LOCAL_ADMIN and (
        not activity.get("assigned_to") or str(activity["assigned_to"]) != identity
    ):
        return jsonify({"error": "Forbidden"}), 403

    if current == "completed":
        return jsonify({"error": "Activity is already completed"}), 400

    # An activity waiting in the pending pool, or freshly assigned, has to be
    # started before it can be completed.
    if current in ("pending", "assigned") and new_status != "in_progress" and role != LOCAL_ADMIN:
        return jsonify({"error": "Must accept before completing"}), 400

    if current == "in_progress" and new_status == "in_progress":
        return jsonify({"error": "Already in progress"}), 400

    now = datetime.now(timezone.utc)
    db.activities.update_one(
        {"_id": ObjectId(activity_id)},
        {"$set": {"status": new_status, "updated_at": now}},
    )

    admin_id = str(activity["assigned_by"])

    if new_status == "in_progress" and current == "pending":
        nid1 = db.notifications.insert_one({
            "user_id": ObjectId(admin_id),
            "type": "activity_accepted",
            "title": "Activity Accepted",
            "message": f"Employee accepted activity '{activity.get('title')}'",
            "activity_id": ObjectId(activity_id),
            "read": False,
            "created_at": now,
        }).inserted_id

        AuditService.log(
            action="create",
            entity_type="notification",
            entity_id=str(nid1),
            performed_by=identity,
            description=f"Activity accepted notification sent to admin {admin_id}",
        )

        notify_user(admin_id, {
            "_id": str(nid1),
            "type": "activity_accepted",
            "title": "Activity Accepted",
            "message": f"Employee accepted activity '{activity.get('title')}'",
            "activity_id": activity_id,
            "read": False,
            "created_at": now.isoformat(),
        })
        notify_badge_update(admin_id)

    if new_status == "completed":
        nid2 = db.notifications.insert_one({
            "user_id": ObjectId(admin_id),
            "type": "activity_completed",
            "title": "Activity Completed",
            "message": f"Activity '{activity.get('title')}' has been completed",
            "activity_id": ObjectId(activity_id),
            "read": False,
            "created_at": now,
        }).inserted_id

        AuditService.log(
            action="create",
            entity_type="notification",
            entity_id=str(nid2),
            performed_by=identity,
            description=f"Activity completed notification sent to admin {admin_id}",
        )

        notify_user(admin_id, {
            "_id": str(nid2),
            "type": "activity_completed",
            "title": "Activity Completed",
            "message": f"Activity '{activity.get('title')}' has been completed",
            "activity_id": activity_id,
            "read": False,
            "created_at": now.isoformat(),
        })
        notify_badge_update(admin_id)

    AuditService.log(
        action="update",
        entity_type="activity",
        entity_id=activity_id,
        performed_by=identity,
        description=f"Activity '{activity.get('title')}' status changed to {new_status}",
    )

    updated = db.activities.find_one({"_id": ObjectId(activity_id)})
    return jsonify(_serialize_activity(updated)), 200


@activities_bp.route("/notifications", methods=["GET"])
@jwt_required()
def list_notifications():
    db = get_db()
    identity = get_jwt_identity()
    notifications = list(
        db.notifications.find({"user_id": ObjectId(identity)}).sort("created_at", -1).limit(50)
    )
    for n in notifications:
        if "_id" in n and isinstance(n["_id"], ObjectId):
            n["_id"] = str(n["_id"])
        if "user_id" in n and isinstance(n["user_id"], ObjectId):
            n["user_id"] = str(n["user_id"])
        if "activity_id" in n and isinstance(n["activity_id"], ObjectId):
            n["activity_id"] = str(n["activity_id"])
    return jsonify(notifications), 200


@activities_bp.route("/notifications/read", methods=["POST"])
@jwt_required()
def mark_notifications_read():
    db = get_db()
    identity = get_jwt_identity()
    result = db.notifications.update_many(
        {"user_id": ObjectId(identity), "read": False},
        {"$set": {"read": True}},
    )
    if result.modified_count > 0:
        AuditService.log(
            action="update",
            entity_type="notification",
            entity_id="",
            performed_by=identity,
            description=f"{result.modified_count} notifications marked as read",
        )
    return jsonify({"ok": True}), 200


@activities_bp.route("/notifications/unread-count", methods=["GET"])
@jwt_required()
def unread_notification_count():
    db = get_db()
    identity = get_jwt_identity()
    count = db.notifications.count_documents({"user_id": ObjectId(identity), "read": False})
    return jsonify({"count": count}), 200


@activities_bp.route("/notifications/send", methods=["POST"])
@jwt_required()
def send_notification():
    db = get_db()
    identity = get_jwt_identity()
    claims = get_jwt()
    data = request.get_json()
    target_user_id = data.get("user_id", "").strip()
    message = data.get("message", "").strip()
    title = data.get("title", "Notification").strip()

    if not target_user_id or not message:
        return jsonify({"error": "user_id and message are required"}), 400
    if not db.users.find_one(company_scope({"_id": to_object_id(target_user_id)})):
        return jsonify({"error": "User not found"}), 404

    sender = db.users.find_one({"_id": ObjectId(identity)}, {"full_name": 1})
    sender_name = sender["full_name"] if sender else "Unknown"

    now = datetime.now(timezone.utc)
    nid = db.notifications.insert_one({
        "user_id": ObjectId(target_user_id),
        "company_id": current_company_id(),
        "type": "manual",
        "title": title,
        "message": f"From {sender_name}: {message}",
        "sender_id": ObjectId(identity),
        "read": False,
        "created_at": now,
    }).inserted_id

    notify_user(target_user_id, {
        "_id": str(nid),
        "type": "manual",
        "title": title,
        "message": f"From {sender_name}: {message}",
        "sender_id": identity,
        "read": False,
        "created_at": now.isoformat(),
    })
    notify_badge_update(target_user_id)

    AuditService.log(
        action="create",
        entity_type="notification",
        entity_id="",
        performed_by=identity,
        description=f"Manual notification sent to user {target_user_id}: {title}",
    )

    return jsonify({"ok": True}), 201


@activities_bp.route("/<activity_id>/note", methods=["PUT"])
@jwt_required()
def update_activity_note(activity_id):
    db = get_db()
    identity = get_jwt_identity()
    claims = get_jwt()

    activity = db.activities.find_one(company_scope({"_id": to_object_id(activity_id)}))
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    role = current_role()
    if role != LOCAL_ADMIN and str(activity["assigned_to"]) != identity:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    note = data.get("note", "").strip() or None

    now = datetime.now(timezone.utc)
    db.activities.update_one(
        {"_id": ObjectId(activity_id)},
        {"$set": {"notes": note, "updated_at": now}},
    )

    AuditService.log(
        action="update",
        entity_type="activity",
        entity_id=activity_id,
        performed_by=identity,
        description=f"Note updated on activity '{activity.get('title')}'",
    )

    return jsonify({"ok": True, "note": note}), 200


@activities_bp.route("/<activity_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_activity(activity_id):
    db = get_db()
    activity = db.activities.find_one(company_scope({"_id": to_object_id(activity_id)}))
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    db.activities.delete_one({"_id": ObjectId(activity_id)})

    AuditService.log(
        action="delete",
        entity_type="activity",
        entity_id=activity_id,
        performed_by=get_jwt_identity(),
        description=f"Activity '{activity.get('title')}' deleted",
    )

    return jsonify({"message": "Activity deleted"}), 200
