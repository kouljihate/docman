from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.models.audit import AuditLogResponse
from app.services.audit_service import AuditService
from app.tenancy import main_admin_required

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("/logs", methods=["GET"])
@jwt_required()
@main_admin_required
def get_logs():
    """Platform-wide audit trail (main administrator only)."""
    raw = request.args.get("entity_type", "")
    entity_types = [t.strip() for t in raw.split(",") if t.strip()] if raw else None
    entity_id = request.args.get("entity_id")
    limit = min(int(request.args.get("limit", 100)), 500)
    skip = max(int(request.args.get("skip", 0)), 0)

    logs = AuditService.get_logs(
        entity_types=entity_types,
        entity_id=entity_id,
        limit=limit,
        skip=skip,
        all_companies=True,
    )
    total = AuditService.count_logs(
        entity_types=entity_types,
        entity_id=entity_id,
        all_companies=True,
    )

    return jsonify({"total": total, "logs": [AuditLogResponse(**log).model_dump(by_alias=True) for log in logs]}), 200


@audit_bp.route("/logs", methods=["DELETE"])
@jwt_required()
@main_admin_required
def clear_logs():
    """Clean the platform-wide audit trail (main administrator only)."""
    raw = request.args.get("entity_type", "")
    entity_types = [t.strip() for t in raw.split(",") if t.strip()] if raw else None
    deleted = AuditService.clear_logs(entity_types=entity_types, all_companies=True)
    return jsonify({"deleted": deleted}), 200
