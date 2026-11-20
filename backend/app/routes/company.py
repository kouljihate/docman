"""Company settings for the signed-in company (local admin)."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import get_db
from app.models.company import CompanyResponse, CompanySettingsUpdate
from app.services.audit_service import AuditService
from app.tenancy import (
    company_member_required,
    current_company_id,
    current_user_id,
    local_admin_required,
)

company_bp = Blueprint("company", __name__, url_prefix="/api/company")


@company_bp.route("/settings", methods=["GET"])
@jwt_required()
@company_member_required
def get_settings():
    db = get_db()
    company_id = current_company_id()
    settings = db.companies.find_one({"_id": company_id}) if company_id else None
    if not settings:
        return jsonify({"error": "Company settings not found"}), 404
    return jsonify(CompanyResponse.from_mongo(settings).model_dump(by_alias=True)), 200


@company_bp.route("/settings", methods=["POST"])
@jwt_required()
@local_admin_required
def save_settings():
    db = get_db()
    company_id = current_company_id()
    existing = db.companies.find_one({"_id": company_id}) if company_id else None
    if not existing:
        return jsonify({"error": "Company settings not found"}), 404

    try:
        settings_data = CompanySettingsUpdate(**(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    update = settings_data.model_dump(by_alias=True)
    update["updated_at"] = datetime.now(timezone.utc)
    db.companies.update_one({"_id": company_id}, {"$set": update})

    AuditService.log(
        action="update",
        entity_type="company_settings",
        entity_id=str(company_id),
        performed_by=current_user_id(),
        description="Company settings updated",
    )

    updated = db.companies.find_one({"_id": company_id})
    return jsonify(CompanyResponse.from_mongo(updated).model_dump(by_alias=True)), 200
