"""Customer/staff requests, stored per company and routed to a local admin."""
import os
import re
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from app.database import get_db
from app.services.audit_service import AuditService
from app.tenancy import (
    CUSTOMER,
    LOCAL_ADMIN,
    company_scope,
    current_company_id,
    current_role,
    current_user_id,
    local_staff_required,
    role_required,
    to_object_id,
)

requests_bp = Blueprint("requests", __name__, url_prefix="/api/requests")

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
REQUESTS_DIR = os.path.join(PROJECT_ROOT, "requests")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


def _safe_folder(folder):
    return os.path.basename(folder) if folder else ""


def _request_query(extra=None):
    query = company_scope(extra)
    if current_role() == CUSTOMER:
        query["created_by"] = to_object_id(get_jwt_identity())
    return query


def _serialize(doc):
    return {
        "foldername": str(doc["_id"]),
        "title": doc.get("title", ""),
        "date": doc.get("created_at").strftime("%Y-%m-%d %H:%M UTC") if isinstance(doc.get("created_at"), datetime) else "",
        "image_count": len(doc.get("screenshots") or []),
        "status": doc.get("status", "open"),
        "created_by_name": doc.get("created_by_name", ""),
    }


def _markdown(doc):
    now_str = doc["created_at"].strftime("%Y-%m-%d %H:%M UTC") if isinstance(doc.get("created_at"), datetime) else ""
    refs = "\n".join(f"![Screenshot {i+1}]({name})" for i, name in enumerate(doc.get("screenshots") or []))
    screenshots = f"\n\n## Screenshots\n\n{refs}" if refs else ""
    return f"""# {doc.get('title', '')}

**Date:** {now_str}
**Author:** {doc.get('created_by_name', '')}

---

{doc.get('content', '')}{screenshots}
"""


@requests_bp.route("/", methods=["GET"])
@jwt_required()
@role_required("local_admin", "local_employee", "customer")
def list_requests():
    db = get_db()
    documents = list(db.requests.find(_request_query()).sort("created_at", -1))
    return jsonify([_serialize(doc) for doc in documents]), 200


@requests_bp.route("/<request_id>", methods=["GET"])
@jwt_required()
@role_required("local_admin", "local_employee", "customer")
def get_request_detail(request_id):
    db = get_db()
    doc = db.requests.find_one(_request_query({"_id": to_object_id(request_id)}))
    if not doc:
        return jsonify({"error": "Request not found"}), 404
    return jsonify(
        {
            "foldername": str(doc["_id"]),
            "title": doc.get("title", ""),
            "date": _serialize(doc)["date"],
            "markdown": _markdown(doc),
            "images": [f"/api/requests/{doc['_id']}/image/{name}" for name in doc.get("screenshots") or []],
            "status": doc.get("status", "open"),
        }
    ), 200


@requests_bp.route("/<request_id>/image/<imagename>", methods=["GET"])
@jwt_required()
@role_required("local_admin", "local_employee", "customer")
def get_request_image(request_id, imagename):
    db = get_db()
    doc = db.requests.find_one(_request_query({"_id": to_object_id(request_id)}))
    if not doc:
        return jsonify({"error": "Request not found"}), 404

    name = secure_filename(imagename)
    if name not in (doc.get("screenshots") or []):
        return jsonify({"error": "Image not found"}), 404

    image_path = os.path.join(REQUESTS_DIR, _safe_folder(doc.get("folder", "")), name)
    if not os.path.isfile(image_path):
        return jsonify({"error": "Image not found"}), 404
    return send_file(image_path)


@requests_bp.route("/", methods=["POST"])
@jwt_required()
@role_required("local_admin", "local_employee", "customer")
def create_request():
    db = get_db()
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    files = request.files.getlist("screenshots")

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not content:
        return jsonify({"error": "Content is required"}), 400

    identity = get_jwt_identity()
    company_id = current_company_id()
    me = db.users.find_one({"_id": ObjectId(identity)}, {"full_name": 1, "local_admin_id": 1, "role": 1})
    now = datetime.now(timezone.utc)

    # Customer requests go to their own local admin; staff requests to the
    # company's first active admin.
    target_admin = None
    if current_role() == CUSTOMER and me and me.get("local_admin_id"):
        target_admin = me["local_admin_id"]
    if target_admin is None:
        admin = db.users.find_one({"company_id": company_id, "role": LOCAL_ADMIN, "is_active": True})
        target_admin = admin["_id"] if admin else None

    request_id = ObjectId()
    folder = str(request_id)
    folder_path = os.path.join(REQUESTS_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)

    saved = []
    for index, upload in enumerate(files, 1):
        if not upload or not upload.filename:
            continue
        ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if ext not in ALLOWED_EXT:
            continue
        name = f"image_{index}.{ext}"
        upload.save(os.path.join(folder_path, name))
        saved.append(name)

    doc = {
        "_id": request_id,
        "company_id": company_id,
        "created_by": ObjectId(identity),
        "created_by_name": (me or {}).get("full_name", ""),
        "target_admin_id": target_admin,
        "title": title,
        "content": content,
        "folder": folder,
        "screenshots": saved,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    db.requests.insert_one(doc)

    # The local admin is notified in-app (no email/git side effects).
    if target_admin:
        from app.socketio_server import notify_badge_update, notify_user

        notification_id = db.notifications.insert_one(
            {
                "user_id": target_admin,
                "company_id": company_id,
                "type": "request_created",
                "title": "New request",
                "message": f"{doc['created_by_name']} submitted: {title}",
                "request_id": request_id,
                "read": False,
                "created_at": now,
            }
        ).inserted_id
        notify_user(
            str(target_admin),
            {
                "_id": str(notification_id),
                "type": "request_created",
                "title": "New request",
                "message": f"{doc['created_by_name']} submitted: {title}",
                "request_id": str(request_id),
                "read": False,
                "created_at": now.isoformat(),
            },
        )
        notify_badge_update(str(target_admin))

    AuditService.log(
        action="create",
        entity_type="request",
        entity_id=str(request_id),
        performed_by=identity,
        description=f"Request '{title}' created",
    )

    return jsonify({"ok": True, "foldername": folder, "message": "Request created"}), 201


@requests_bp.route("/<request_id>/status", methods=["PUT"])
@jwt_required()
@local_staff_required
def update_request_status(request_id):
    db = get_db()
    doc = db.requests.find_one({"_id": to_object_id(request_id), "company_id": current_company_id()})
    if not doc:
        return jsonify({"error": "Request not found"}), 404

    status = (request.get_json(silent=True) or {}).get("status", "").strip()
    if status not in ("open", "in_progress", "closed"):
        return jsonify({"error": "Invalid status"}), 400

    db.requests.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
    )
    AuditService.log(
        action="update",
        entity_type="request",
        entity_id=str(doc["_id"]),
        performed_by=current_user_id(),
        description=f"Request '{doc.get('title')}' marked {status}",
    )
    return jsonify({"ok": True, "status": status}), 200
