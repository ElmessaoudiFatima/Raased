import os

from flask import Blueprint, current_app, jsonify, request, send_file

from extensions import db
from models import AuditLog, Cargo, Organization, OrganizationDocument, User
from security import require_role, utcnow
from service import record_audit

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _org_documents(org_id):
    return OrganizationDocument.query.filter_by(organization_id=org_id).all()


def _managers_of(org_id):
    return User.query.filter_by(organization_id=org_id, role="MANAGER").all()


def _org_small(org):
    return {
        "id": org.id,
        "name": org.name,
        "legal_id": org.legal_id,
        "country": org.country,
        "city": org.city,
        "phone": org.phone,
        "email": org.email,
        "website": org.website,
        "status": org.status,
        "rejection_reason": org.rejection_reason,
        "reviewed_at": org.reviewed_at.isoformat() if org.reviewed_at else None,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


@admin_bp.get("/organizations")
@require_role("ADMIN")
def organizations(current_user):
    status = (request.args.get("status") or "").upper()
    query = Organization.query
    if status:
        query = query.filter_by(status=status)
    orgs = query.order_by(Organization.created_at.desc()).all()
    data = []
    for org in orgs:
        item = _org_small(org)
        managers = _managers_of(org.id)
        manager = managers[0] if managers else None
        item["manager"] = (
            {
                "id": manager.id,
                "first_name": manager.first_name,
                "last_name": manager.last_name,
                "email": manager.email,
                "job_title": manager.job_title,
                "phone": manager.phone,
                "email_verified": manager.email_verified,
            }
            if manager
            else None
        )
        item["documents_count"] = len(_org_documents(org.id))
        data.append(item)
    return jsonify(organizations=data)


@admin_bp.get("/organizations/<organization_id>")
@require_role("ADMIN")
def organization_detail(organization_id, current_user):
    org = db.session.get(Organization, organization_id)
    if not org:
        return jsonify(error="Organisation introuvable."), 404
    item = _org_small(org)
    item["managers"] = [
        {
            "id": m.id,
            "first_name": m.first_name,
            "last_name": m.last_name,
            "email": m.email,
            "job_title": m.job_title,
            "phone": m.phone,
            "email_verified": m.email_verified,
            "account_status": m.account_status,
        }
        for m in _managers_of(org.id)
    ]
    item["documents"] = [
        {
            "id": d.id,
            "document_type": d.document_type,
            "file_url": d.file_url,
            "download_url": f"/api/admin/documents/{d.id}/download",
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in _org_documents(org.id)
    ]
    return jsonify(organization=item)


@admin_bp.get("/documents/<document_id>/download")
@require_role("ADMIN")
def document_download(document_id, current_user):
    doc = db.session.get(OrganizationDocument, document_id)
    if not doc:
        return jsonify(error="Document introuvable."), 404
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.file_url.removeprefix("uploads/"))
    if not os.path.exists(path):
        return jsonify(error="Fichier introuvable sur le serveur."), 404
    return send_file(path, as_attachment=False, mimetype="application/octet-stream")


@admin_bp.patch("/organizations/<organization_id>/approve")
@require_role("ADMIN")
def organization_approve(organization_id, current_user):
    org = db.session.get(Organization, organization_id)
    if not org:
        return jsonify(error="Organisation introuvable."), 404
    org.status = "APPROVED"
    org.reviewed_by = current_user.id
    org.reviewed_at = utcnow()
    org.rejection_reason = None
    managers = _managers_of(org.id)
    for manager in managers:
        if manager.account_status == "INVITED" and manager.password:
            manager.account_status = "ACTIVE"
        manager.is_active = True
    db.session.commit()
    record_audit(
        "ORG_APPROVED",
        actor=current_user,
        target_type="ORGANIZATION",
        target_id=org.id,
        details=f"Organisation « {org.name} » approuvée par l'admin",
        ip=request.remote_addr,
    )
    return jsonify(organization=_org_small(org), message="Demande approuvée.")


@admin_bp.patch("/organizations/<organization_id>/reject")
@require_role("ADMIN")
def organization_reject(organization_id, current_user):
    body = request.get_json(silent=True) or {}
    org = db.session.get(Organization, organization_id)
    if not org:
        return jsonify(error="Organisation introuvable."), 404
    org.status = "REJECTED"
    org.reviewed_by = current_user.id
    org.reviewed_at = utcnow()
    org.rejection_reason = (body.get("rejection_reason") or "Demande rejetée.").strip()
    managers = _managers_of(org.id)
    for manager in managers:
        manager.is_active = False
        manager.account_status = "DISABLED"
    db.session.commit()
    record_audit(
        "ORG_REJECTED",
        actor=current_user,
        target_type="ORGANIZATION",
        target_id=org.id,
        details=f"Organisation « {org.name} » rejetée : {org.rejection_reason}",
        ip=request.remote_addr,
    )
    return jsonify(organization=_org_small(org), message="Demande rejetée.")


@admin_bp.get("/stats")
@require_role("ADMIN")
def stats(current_user):
    pending = Organization.query.filter_by(status="PENDING").count()
    approved = Organization.query.filter_by(status="APPROVED").count()
    rejected = Organization.query.filter_by(status="REJECTED").count()
    drivers = User.query.filter_by(role="DRIVER").count()
    managers = User.query.filter_by(role="MANAGER").count()
    admins = User.query.filter_by(role="ADMIN").count()
    total_users = User.query.count()
    cargos = Cargo.query.count()
    in_transit = Cargo.query.filter_by(status="IN_TRANSIT").count()

    # MENA country distribution
    all_orgs = Organization.query.all()
    country_counts = {}
    for o in all_orgs:
        c = o.country or "Maroc"
        country_counts[c] = country_counts.get(c, 0) + 1

    mena_distribution = [{"country": k, "count": v} for k, v in sorted(country_counts.items(), key=lambda x: x[1], reverse=True)]

    recent_audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()

    return jsonify(
        stats={
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_organizations": len(all_orgs),
            "managers": managers,
            "drivers": drivers,
            "admins": admins,
            "total_users": total_users,
            "cargos": cargos,
            "in_transit": in_transit,
            "mena_distribution": mena_distribution,
            "recent_audits": [a.to_dict() for a in recent_audits],
        }
    )


@admin_bp.get("/users")
@require_role("ADMIN")
def get_users(current_user):
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify(
        users=[
            {
                "id": u.id,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "phone": u.phone,
                "job_title": u.job_title,
                "role": u.role,
                "avatar_url": u.avatar_url,
                "account_status": u.account_status,
                "is_active": u.is_active,
                "email_verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "organization": (
                    {
                        "id": u.organization.id,
                        "name": u.organization.name,
                        "city": u.organization.city,
                        "country": u.organization.country,
                        "status": u.organization.status,
                    }
                    if u.organization
                    else None
                ),
            }
            for u in users
        ]
    )


@admin_bp.patch("/users/<user_id>/status")
@require_role("ADMIN")
def toggle_user_status(user_id, current_user):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Utilisateur introuvable."), 404
    if user.id == current_user.id:
        return jsonify(error="Vous ne pouvez pas modifier votre propre statut."), 400

    body = request.get_json(silent=True) or {}
    action = body.get("action")
    if action not in ("enable", "disable"):
        return jsonify(error="Action invalide."), 400

    user.is_active = action == "enable"
    user.account_status = "ACTIVE" if action == "enable" else "DISABLED"
    db.session.commit()

    record_audit(
        "USER_STATUS_CHANGE",
        actor=current_user,
        target_type="USER",
        target_id=user.id,
        details=f"Statut utilisateur changé en : {action}",
        ip=request.remote_addr,
    )
    return jsonify(message="Statut utilisateur mis à jour.", is_active=user.is_active)


@admin_bp.delete("/users/<user_id>")
@require_role("ADMIN")
def delete_user(user_id, current_user):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Utilisateur introuvable."), 404
    if user.id == current_user.id:
        return jsonify(error="Vous ne pouvez pas supprimer votre propre compte."), 400

    # Unassign assigned cargos if driver
    cargos = Cargo.query.filter_by(assigned_driver_id=user.id).all()
    for c in cargos:
        c.assigned_driver_id = None

    email = user.email
    role = user.role
    db.session.delete(user)
    db.session.commit()

    record_audit(
        "USER_DELETED",
        actor=current_user,
        target_type="USER",
        target_id=user_id,
        details=f"Compte {email} ({role}) supprimé par l'administrateur",
        ip=request.remote_addr,
    )
    return jsonify(message="Utilisateur supprimé avec succès.")


@admin_bp.get("/audit")
@require_role("ADMIN")
def get_audit_logs(current_user):
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify(logs=[l.to_dict() for l in logs])