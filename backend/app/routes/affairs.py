from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.models.affair import AffairCreate, AffairResponse, AffairUpdate
from app.services.audit_service import AuditService
from app.socketio_server import notify_badge_update, notify_user
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    LOCAL_EMPLOYEE,
    company_scope,
    current_company_id,
    current_user_id,
    is_customer,
    local_admin_required,
    role_required,
    to_object_id,
)

affairs_bp = Blueprint("affairs", __name__, url_prefix="/api/affairs")

# Activities generated from an affair can be handled by an employee or by
# the local manager himself.
ASSIGNABLE_ROLES = (LOCAL_ADMIN, LOCAL_EMPLOYEE)


def _services_for(db, service_ids):
    """Return the company's service documents for `service_ids`.

    `None` means one of the ids is invalid or belongs to another company.
    """
    ids = []
    for sid in service_ids or []:
        oid = to_object_id(sid)
        if oid is None:
            return None
        ids.append(oid)
    if not ids:
        return []
    services = list(db.services.find(company_scope({"_id": {"$in": ids}})))
    if len({s["_id"] for s in services}) != len(set(ids)):
        return None
    order = {sid: index for index, sid in enumerate(ids)}
    services.sort(key=lambda s: order.get(s["_id"], 0))
    return services


def _assignee_for(db, user_id):
    """Return a local admin or employee of the caller's company, or None."""
    return db.users.find_one(
        company_scope(
            {"_id": to_object_id(user_id), "role": {"$in": list(ASSIGNABLE_ROLES)}}
        )
    )


def _generate_activities(db, affair, services, assignee, performed_by):
    """Create one activity per service and assign it to `assignee`.

    Services that already have an activity on this affair are skipped so the
    action can be retried without duplicates. Returns the created ids.
    """
    existing = {
        a.get("service_id")
        for a in db.activities.find({"affair_id": affair["_id"]}, {"service_id": 1})
    }
    now = datetime.now(timezone.utc)
    created = []
    for service in services:
        if service["_id"] in existing:
            continue
        title = f"{affair['name']} - {service['name']}"
        doc = {
            "title": title,
            "description": service.get("description") or affair.get("notes"),
            "assigned_to": assignee["_id"],
            "assigned_by": ObjectId(performed_by),
            "customer_id": affair["customer_id"],
            "company_id": affair["company_id"],
            "affair_id": affair["_id"],
            "service_id": service["_id"],
            "task_ids": list(service.get("task_ids") or []),
            "status": "pending",
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }
        activity_id = db.activities.insert_one(doc).inserted_id
        created.append(activity_id)

        notif_id = db.notifications.insert_one(
            {
                "user_id": assignee["_id"],
                "company_id": affair["company_id"],
                "type": "activity_assigned",
                "title": "New Activity Assigned",
                "message": f"You have been assigned a new activity: {title}",
                "activity_id": activity_id,
                "affair_id": affair["_id"],
                "read": False,
                "created_at": now,
            }
        ).inserted_id

        notify_user(
            str(assignee["_id"]),
            {
                "_id": str(notif_id),
                "type": "activity_assigned",
                "title": "New Activity Assigned",
                "message": f"You have been assigned a new activity: {title}",
                "activity_id": str(activity_id),
                "read": False,
                "created_at": now.isoformat(),
            },
        )
        notify_badge_update(str(assignee["_id"]))

        AuditService.log(
            action="create",
            entity_type="activity",
            entity_id=str(activity_id),
            performed_by=performed_by,
            description=f"Activity '{title}' generated from affair '{affair['name']}'",
        )
    return created


def _affair_pipeline(match):
    return [
        {"$match": match},
        {"$sort": {"name": 1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "customer_id",
                "foreignField": "_id",
                "as": "customer",
            }
        },
        {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "users",
                "localField": "assigned_to",
                "foreignField": "_id",
                "as": "assignee",
            }
        },
        {"$unwind": {"path": "$assignee", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "services",
                "localField": "service_ids",
                "foreignField": "_id",
                "as": "services",
            }
        },
        {
            "$addFields": {
                "customer_name": "$customer.full_name",
                "assigned_to_name": "$assignee.full_name",
                "assigned_to_role": "$assignee.role",
                "service_names": {
                    "$map": {"input": "$services", "as": "s", "in": "$$s.name"}
                },
            }
        },
        {"$project": {"customer": 0, "assignee": 0, "services": 0}},
    ]


def _with_activity_stats(db, affairs):
    if not affairs:
        return affairs
    counts = {}
    rows = db.activities.aggregate(
        [
            {"$match": {"affair_id": {"$in": [a["_id"] for a in affairs]}}},
            {
                "$group": {
                    "_id": {"affair_id": "$affair_id", "status": "$status"},
                    "n": {"$sum": 1},
                }
            },
        ]
    )
    for row in rows:
        stats = counts.setdefault(
            row["_id"]["affair_id"],
            {"activity_count": 0, "completed_activity_count": 0},
        )
        stats["activity_count"] += row["n"]
        if row["_id"].get("status") == "completed":
            stats["completed_activity_count"] += row["n"]
    for affair in affairs:
        affair.update(
            counts.get(
                affair["_id"],
                {"activity_count": 0, "completed_activity_count": 0},
            )
        )
    return affairs


def _load_affairs(db, match):
    affairs = list(db.affairs.aggregate(_affair_pipeline(match)))
    return _with_activity_stats(db, affairs)


def _serialize(affair):
    return AffairResponse(**affair).model_dump(by_alias=True)


@affairs_bp.route("/", methods=["POST"])
@jwt_required()
@local_admin_required
def create_affair():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    try:
        affair_data = AffairCreate(**payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    customer = db.users.find_one(
        company_scope({"_id": to_object_id(affair_data.customer_id), "role": CUSTOMER})
    )
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    services = _services_for(db, affair_data.service_ids)
    if services is None:
        return jsonify({"error": "One or more services were not found"}), 404

    assignee = None
    if affair_data.assigned_to:
        assignee = _assignee_for(db, affair_data.assigned_to)
        if not assignee:
            return jsonify({"error": "Assigned user must be an employee or local manager of your company"}), 400
    if services and affair_data.generate_activities and not assignee:
        return jsonify({"error": "Select the employee or local manager who will handle the activities"}), 400

    now = datetime.now(timezone.utc)
    affair_dict = affair_data.model_dump(by_alias=True)
    affair_dict["customer_id"] = customer["_id"]
    affair_dict["company_id"] = customer.get("company_id") or current_company_id()
    affair_dict["service_ids"] = [s["_id"] for s in services]
    affair_dict["assigned_to"] = assignee["_id"] if assignee else None
    affair_dict["created_by"] = ObjectId(current_user_id())
    affair_dict["created_at"] = now
    affair_dict["updated_at"] = now
    affair_dict.pop("generate_activities", None)

    result = db.affairs.insert_one(affair_dict)
    affair_dict["_id"] = result.inserted_id

    if services and assignee and affair_data.generate_activities:
        _generate_activities(db, affair_dict, services, assignee, current_user_id())

    AuditService.log(
        action="create",
        entity_type="affair",
        entity_id=str(result.inserted_id),
        performed_by=current_user_id(),
        description=f"Affair '{affair_data.name}' created for customer",
    )

    return jsonify(_serialize(_load_affairs(db, {"_id": result.inserted_id})[0])), 201


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

    return jsonify([_serialize(a) for a in _load_affairs(db, query)]), 200


@affairs_bp.route("/<affair_id>", methods=["GET"])
@jwt_required()
@role_required("main_admin", "local_admin", "local_employee", "customer")
def get_affair(affair_id):
    db = get_db()
    query = company_scope({"_id": to_object_id(affair_id)})
    if is_customer():
        query["customer_id"] = to_object_id(get_jwt_identity())

    affairs = _load_affairs(db, query)
    if not affairs:
        return jsonify({"error": "Affair not found"}), 404
    return jsonify(_serialize(affairs[0])), 200


@affairs_bp.route("/<affair_id>", methods=["PUT"])
@jwt_required()
@local_admin_required
def update_affair(affair_id):
    db = get_db()
    payload = request.get_json(silent=True) or {}
    service_ids = payload.pop("service_ids", None)
    try:
        update_data = AffairUpdate(**payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update_dict = {
        k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None
    }
    if service_ids is not None:
        services = _services_for(db, service_ids)
        if services is None:
            return jsonify({"error": "One or more services were not found"}), 404
        update_dict["service_ids"] = [s["_id"] for s in services]
    if "assigned_to" in update_dict:
        assignee = _assignee_for(db, update_dict["assigned_to"])
        if not assignee:
            return jsonify({"error": "Assigned user must be an employee or local manager of your company"}), 400
        update_dict["assigned_to"] = assignee["_id"]
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

    return jsonify(_serialize(_load_affairs(db, {"_id": old["_id"]})[0])), 200


@affairs_bp.route("/<affair_id>/activities", methods=["POST"])
@jwt_required()
@local_admin_required
def generate_affair_activities(affair_id):
    """Generate the affair's activities (one per service) on demand."""
    db = get_db()
    affair = db.affairs.find_one(company_scope({"_id": to_object_id(affair_id)}))
    if not affair:
        return jsonify({"error": "Affair not found"}), 404

    services = _services_for(db, [str(s) for s in affair.get("service_ids") or []])
    if not services:
        return jsonify({"error": "Attach at least one service to this affair first"}), 400

    if not affair.get("assigned_to"):
        return jsonify({"error": "Assign this affair to an employee or local manager first"}), 400
    assignee = _assignee_for(db, str(affair["assigned_to"]))
    if not assignee:
        return jsonify({"error": "The assigned user is no longer available"}), 400

    created = _generate_activities(db, affair, services, assignee, current_user_id())
    return (
        jsonify({"created": len(created), "activity_ids": [str(c) for c in created]}),
        201 if created else 200,
    )


@affairs_bp.route("/<affair_id>", methods=["DELETE"])
@jwt_required()
@local_admin_required
def delete_affair(affair_id):
    db = get_db()
    affair = db.affairs.find_one(company_scope({"_id": to_object_id(affair_id)}))
    if not affair:
        return jsonify({"error": "Affair not found"}), 404

    activity_ids = [
        a["_id"] for a in db.activities.find({"affair_id": affair["_id"]}, {"_id": 1})
    ]
    if activity_ids:
        db.notifications.delete_many({"activity_id": {"$in": activity_ids}})
        db.activities.delete_many({"_id": {"$in": activity_ids}})

    db.affairs.delete_one({"_id": affair["_id"]})

    AuditService.log(
        action="delete",
        entity_type="affair",
        entity_id=str(affair["_id"]),
        performed_by=current_user_id(),
        description=f"Affair '{affair.get('name')}' deleted",
    )

    return jsonify({"message": "Affair deleted"}), 200
