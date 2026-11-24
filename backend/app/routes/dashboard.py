from datetime import datetime, timedelta, timezone

from bson import ObjectId
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import get_db
from app.tenancy import (
    CUSTOMER,
    LOCAL_EMPLOYEE,
    company_scope,
    current_company_id,
    current_role,
    to_object_id,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _empty():
    return {
        "total_tasks": 0,
        "monthly_tasks": 0,
        "tasks_by_status": {},
        "tasks_by_priority": {},
        "users_count": 0,
        "customers_count": 0,
        "services_count": 0,
        "affairs_count": 0,
        "total_activities": 0,
        "companies_count": 0,
        "documents_count": 0,
        "payments_due_count": 0,
        "payments_overdue_count": 0,
        "open_tasks": None,
        "completed_tasks": None,
        "recent_activities": [],
    }


@dashboard_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    db = get_db()
    identity = get_jwt_identity()
    role = current_role()

    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    board = _empty()
    task_query = company_scope()

    if role == LOCAL_EMPLOYEE:
        task_query["assigned_to"] = ObjectId(identity)
    elif role == CUSTOMER:
        affairs = list(
            db.affairs.find({"customer_id": ObjectId(identity), "company_id": current_company_id()}, {"_id": 1})
        )
        affair_ids = [a["_id"] for a in affairs]
        if not affair_ids:
            return jsonify({**board, "recent_activities": []}), 200
        task_query["affair_id"] = {"$in": affair_ids}

    try:
        board["total_tasks"] = db.tasks.count_documents(task_query)
        board["monthly_tasks"] = db.tasks.count_documents({**task_query, "created_at": {"$gte": first_of_month}})
        board["tasks_by_status"] = {
            row["_id"]: row["count"]
            for row in db.tasks.aggregate([{"$match": task_query}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}])
        }
        board["tasks_by_priority"] = {
            row["_id"]: row["count"]
            for row in db.tasks.aggregate([{"$match": task_query}, {"$group": {"_id": "$priority", "count": {"$sum": 1}}}])
        }

        user_scope = company_scope()
        board["users_count"] = db.users.count_documents({**user_scope, "is_active": True})
        board["customers_count"] = db.users.count_documents({**user_scope, "role": CUSTOMER})
        board["services_count"] = db.services.count_documents(company_scope())
        board["affairs_count"] = db.affairs.count_documents(company_scope())
        board["documents_count"] = db.documents.count_documents(company_scope())
        board["total_activities"] = db.activities.count_documents(company_scope())

        if role == CUSTOMER:
            board["open_tasks"] = db.tasks.count_documents({**task_query, "status": {"$in": ["pending", "in_progress"]}})
            board["completed_tasks"] = db.tasks.count_documents({**task_query, "status": "completed"})

        if role == "main_admin":
            board["companies_count"] = db.companies.count_documents({})

        # Payment reminders of the local admin: pending payments already past
        # their due date, and those falling due within the coming week.
        if role == "local_admin":
            pending_payments = {**company_scope(), "status": "pending"}
            board["payments_overdue_count"] = db.payments.count_documents(
                {**pending_payments, "due_date": {"$lt": now}}
            )
            board["payments_due_count"] = db.payments.count_documents(
                {**pending_payments, "due_date": {"$lt": now + timedelta(days=7)}}
            )

        recent_match = company_scope() if role != CUSTOMER else {"company_id": current_company_id(), "customer_id": ObjectId(identity)}
        recent = list(db.activities.find(recent_match).sort("created_at", -1).limit(10))
        board["recent_activities"] = [
            {
                "id": str(a.get("_id", "")),
                "action": "create",
                "entity_type": "activity",
                "description": a.get("title", ""),
                "performed_by_name": "",
                "created_at": a["created_at"].isoformat() if isinstance(a.get("created_at"), datetime) else "",
            }
            for a in recent
        ]
        return jsonify(board), 200
    except Exception:
        return jsonify(_empty()), 200


@dashboard_bp.route("/assignations", methods=["GET"])
@jwt_required()
def assignations():
    db = get_db()
    identity = get_jwt_identity()
    role = current_role()

    query = company_scope()
    if role == LOCAL_EMPLOYEE:
        query["assigned_to"] = ObjectId(identity)

    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$assigned_to", "task_count": {"$sum": 1}}},
        {"$lookup": {"from": "users", "localField": "_id", "foreignField": "_id", "as": "user"}},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {"employee_name": "$user.full_name", "employee_username": "$user.username", "task_count": 1}},
    ]
    return jsonify(list(db.tasks.aggregate(pipeline))), 200


@dashboard_bp.route("/employee-stats", methods=["GET"])
@jwt_required()
def employee_stats():
    db = get_db()
    identity = get_jwt_identity()
    if current_role() != LOCAL_EMPLOYEE:
        return jsonify({"error": "Employee access required"}), 403

    me = ObjectId(identity)
    company_id = current_company_id()
    base = {"assigned_to": me, "company_id": company_id}

    recent = list(db.activities.find(base).sort("created_at", -1).limit(10))
    processed = []
    for activity in recent:
        entry = {}
        for key, value in activity.items():
            if isinstance(value, ObjectId):
                entry[key] = str(value)
            elif isinstance(value, datetime):
                entry[key] = value.isoformat()
            elif key == "task_ids" and isinstance(value, list):
                entry[key] = [str(v) if isinstance(v, ObjectId) else v for v in value]
            else:
                entry[key] = value
        processed.append(entry)

    return jsonify(
        {
            "pending_activities": db.activities.count_documents({**base, "status": "pending"}),
            "in_progress_activities": db.activities.count_documents({**base, "status": "in_progress"}),
            "completed_activities": db.activities.count_documents({**base, "status": "completed"}),
            "unread_notifications": db.notifications.count_documents({"user_id": me, "read": False}),
            "recent_activities": processed,
        }
    ), 200
