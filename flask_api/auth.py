import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from email_service import send_code_email
from extensions import db
from models import Organization, OrganizationDocument, User
from security import (
    create_access_token,
    create_password_token,
    hash_password,
    require_role,
    utcnow,
    verify_password,
)
from service import (
    consume_invitation,
    record_audit,
    send_invitation_for,
    send_otp_to_email,
    validate_invitation_token,
    verify_last_code,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ALLOWED_DOC_EXT = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_DOC_TYPES = {"COMPANY_CERTIFICATE", "RESPONSIBLE_ID"}


def _serialize_me(user: User):
    data = user.to_dict(include_org=True)
    return data


def _valid_email(value):
    if not value or "@" not in value or "." not in value.split("@")[-1]:
        return False
    return True


def _password_ok(password):
    return isinstance(password, str) and len(password) >= 8


def _json_body():
    return request.get_json(silent=True) or {}


@auth_bp.post("/login")
def login():
    body = _json_body()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.password or not user.is_active or user.account_status != "ACTIVE":
        return jsonify(error="Email ou mot de passe incorrect."), 401
    if not user.email_verified:
        return jsonify(error="Votre adresse e-mail n'est pas encore vérifiée."), 401
    if not verify_password(password, user.password):
        return jsonify(error="Email ou mot de passe incorrect."), 401
    if user.role in ("MANAGER", "DRIVER") and user.organization:
        if user.organization.status != "APPROVED":
            return jsonify(
                error="L'entreprise n'est pas encore approuvée par l'administrateur Raased."
            ), 403
    token = create_access_token(user)
    record_audit("AUTH_LOGIN", actor=user, target_type="USER", target_id=user.id, details=f"Connexion réussie ({user.role})", ip=request.remote_addr)
    return jsonify(access_token=token, token_type="bearer", user=_serialize_me(user))


@auth_bp.post("/register")
def register():
    body = _json_body()
    org = body.get("organization") or {}
    mgr = body.get("manager") or {}

    required_org = ["name", "legal_id", "country", "city", "phone", "address", "email"]
    required_mgr = ["first_name", "last_name", "email", "job_title", "phone"]

    for field in required_org:
        if not org.get(field):
            return jsonify(error=f"Le champ organisation « {field} » est requis."), 400
    for field in required_mgr:
        if not mgr.get(field):
            return jsonify(error=f"Le champ responsable « {field} » est requis."), 400

    if not _valid_email(org.get("email")) or not _valid_email(mgr.get("email")):
        return jsonify(error="Adresse e-mail invalide."), 400

    if User.query.filter_by(email=(mgr["email"].strip().lower())).first():
        return jsonify(error="Un compte existe déjà avec cette adresse e-mail."), 409

    organization = Organization(
        name=org["name"].strip(),
        legal_id=str(org["legal_id"]).strip(),
        country=org.get("country", "Maroc").strip(),
        city=org["city"].strip(),
        phone=org["phone"].strip(),
        address=org["address"].strip(),
        website=(org.get("website") or "").strip() or None,
        email=org["email"].strip().lower(),
        status="PENDING",
    )
    db.session.add(organization)
    db.session.flush()

    manager = User(
        organization_id=organization.id,
        first_name=mgr["first_name"].strip(),
        last_name=mgr["last_name"].strip(),
        job_title=(mgr.get("job_title") or "").strip() or None,
        phone=(mgr.get("phone") or "").strip() or None,
        email=mgr["email"].strip().lower(),
        password=None,
        role="MANAGER",
        email_verified=False,
        account_status="INVITED",
        is_active=True,
    )
    db.session.add(manager)
    db.session.commit()

    record = send_otp_to_email(manager, "REGISTER", "vérification de votre adresse e-mail")
    dev_code = record.code if not current_app.config.get("SMTP_HOST") else None

    return (
        jsonify(
            user_id=manager.id,
            organization_id=organization.id,
            email=manager.email,
            dev_code=dev_code,
            message="Un code de vérification a été envoyé à votre adresse e-mail responsable.",
        ),
        201,
    )


@auth_bp.post("/register/resend")
def register_resend():
    body = _json_body()
    user = db.session.get(User, body.get("user_id"))
    if not user or user.account_status != "INVITED":
        return jsonify(error="Compte introuvable ou déjà activé."), 404
    record = send_otp_to_email(user, "REGISTER", "vérification de votre adresse e-mail")
    dev_code = record.code if not current_app.config.get("SMTP_HOST") else None
    return jsonify(
        dev_code=dev_code,
        message="Un nouveau code de vérification vient d'être envoyé."
    )


@auth_bp.post("/register/verify")
def register_verify():
    body = _json_body()
    user = db.session.get(User, body.get("user_id"))
    if not user:
        return jsonify(error="Compte introuvable."), 404
    ok, msg = verify_last_code(user.id, "REGISTER", body.get("code") or "")
    if not ok:
        return jsonify(error=msg), 400
    user.email_verified = True
    user.email_verified_at = utcnow()
    db.session.commit()
    return jsonify(
        password_token=create_password_token(user.id),
        user_id=user.id,
        message="E-mail vérifié. Définissez maintenant votre mot de passe.",
    )


@auth_bp.post("/register/complete")
def register_complete():
    from security import _decode

    body = _json_body()
    token = body.get("password_token")
    password = body.get("password") or ""
    confirm = body.get("confirm_password") or ""

    payload = _decode(token) if token else None
    if not payload or payload.get("type") != "password":
        return jsonify(error="Jeton de finalisation invalide ou expiré."), 400
    if not _password_ok(password):
        return jsonify(error="Le mot de passe doit contenir au moins 8 caractères."), 400
    if password != confirm:
        return jsonify(error="Les mots de passe ne correspondent pas."), 400

    user = db.session.get(User, payload["sub"])
    if not user:
        return jsonify(error="Compte introuvable."), 404
    user.password = hash_password(password)
    user.account_status = "ACTIVE"
    user.is_active = True
    user.email_verified = True
    user.email_verified_at = utcnow()
    db.session.commit()

    token2 = create_access_token(user)
    return jsonify(
        access_token=token2,
        token_type="bearer",
        user=_serialize_me(user),
        message="Compte Raased créé avec succès.",
    )


@auth_bp.post("/organizations/<organization_id>/documents")
@require_role("MANAGER")
def upload_documents(organization_id, current_user):
    org = db.session.get(Organization, organization_id)
    if not org or org.id != current_user.organization_id:
        return jsonify(error="Organisation introuvable."), 404

    uploaded = []
    for doc_type in ALLOWED_DOC_TYPES:
        file = request.files.get(doc_type)
        if not file or file.filename == "":
            continue
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_DOC_EXT:
            return jsonify(error=f"Fichier non supporté pour {doc_type}. PDF, JPG ou PNG attendu."), 400
        folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "documents", organization_id)
        os.makedirs(folder, exist_ok=True)
        safe = secure_filename(filename)
        stored = f"{org.id}_{doc_type}{ext}"
        file.save(os.path.join(folder, stored))
        doc = OrganizationDocument(
            organization_id=org.id,
            document_type=doc_type,
            file_url=f"uploads/documents/{organization_id}/{stored}",
        )
        db.session.add(doc)
        uploaded.append(doc)
    db.session.commit()

    return jsonify(
        documents=[
            {
                "id": d.id,
                "document_type": d.document_type,
                "file_url": d.file_url,
                "download_url": f"/api/admin/documents/{d.id}/download",
            }
            for d in uploaded
        ],
        message="Documents enregistrés. Votre demande sera examinée par l'administrateur.",
    )


@auth_bp.post("/forgot-password")
def forgot_password():
    body = _json_body()
    email = (body.get("email") or "").strip().lower()
    if not _valid_email(email):
        return jsonify(error="Adresse e-mail invalide."), 400

    user = User.query.filter_by(email=email).first()
    dev_code = None
    if user and user.password and user.is_active and user.account_status in ("ACTIVE", "INVITED"):
        record = send_otp_to_email(user, "RESET", "réinitialisation de votre mot de passe")
        dev_code = record.code if not current_app.config.get("SMTP_HOST") else None
    return jsonify(
        dev_code=dev_code,
        message="Si un compte existe avec cette adresse, un code de vérification a été envoyé."
    )


@auth_bp.post("/forgot-password/resend")
def forgot_password_resend():
    body = _json_body()
    email = (body.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and user.password and user.is_active:
        record = send_otp_to_email(user, "RESET", "réinitialisation de votre mot de passe")
        dev_code = record.code if not current_app.config.get("SMTP_HOST") else None
        return jsonify(
            dev_code=dev_code,
            message="Un nouveau code de vérification vient d'être envoyé."
        )
    return jsonify(error="Aucun compte actif ne correspond à cette adresse."), 404


@auth_bp.post("/forgot-password/verify")
def forgot_password_verify():
    body = _json_body()
    email = (body.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="Aucun compte ne correspond à cette adresse."), 404
    ok, msg = verify_last_code(user.id, "RESET", body.get("code") or "")
    if not ok:
        return jsonify(error=msg), 400
    return jsonify(
        password_token=create_password_token(user.id),
        message="Code confirmé. Vous pouvez définir un nouveau mot de passe.",
    )


@auth_bp.post("/forgot-password/reset")
def forgot_password_reset():
    from security import _decode

    body = _json_body()
    token = body.get("password_token")
    password = body.get("password") or ""
    confirm = body.get("confirm_password") or ""

    payload = _decode(token) if token else None
    if not payload or payload.get("type") != "password":
        return jsonify(error="Jeton invalide ou expiré."), 400
    if not _password_ok(password):
        return jsonify(error="Le mot de passe doit contenir au moins 8 caractères."), 400
    if password != confirm:
        return jsonify(error="Les mots de passe ne correspondent pas."), 400

    user = db.session.get(User, payload["sub"])
    if not user:
        return jsonify(error="Compte introuvable."), 404
    user.password = hash_password(password)
    user.is_active = True
    db.session.commit()
    return jsonify(message="Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.")


@auth_bp.get("/me")
@require_role("ADMIN", "MANAGER", "DRIVER")
def me(current_user):
    return jsonify(user=_serialize_me(current_user))


@auth_bp.get("/invitations/validate")
def invitations_validate():
    token = request.args.get("token", "")
    result, error = validate_invitation_token(token)
    if error:
        return jsonify(error=error), 400
    inv, user = result
    org_name = user.organization.name if user.organization else None
    return jsonify(
        valid=True,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role,
        organization_name=org_name,
    )


@auth_bp.post("/invitations/accept")
def invitations_accept():
    body = _json_body()
    token = body.get("token") or ""
    password = body.get("password") or ""
    confirm = body.get("confirm_password") or ""

    result, error = validate_invitation_token(token)
    if error:
        return jsonify(error=error), 400
    inv, user = result

    if not _password_ok(password):
        return jsonify(error="Le mot de passe doit contenir au moins 8 caractères."), 400
    if password != confirm:
        return jsonify(error="Les mots de passe ne correspondent pas."), 400

    consume_invitation(user, inv, password)
    access_token = create_access_token(user)
    return jsonify(
        access_token=access_token,
        token_type="bearer",
        user=_serialize_me(user),
        message="Votre compte est activé. Bienvenue sur Raased !",
    )


@auth_bp.patch("/profile")
@require_role("ADMIN", "MANAGER", "DRIVER")
def update_profile(current_user):
    body = _json_body()
    first_name = (body.get("first_name") or "").strip()
    last_name = (body.get("last_name") or "").strip()
    phone = (body.get("phone") or "").strip()
    job_title = (body.get("job_title") or "").strip()
    avatar_url = body.get("avatar_url")

    if first_name:
        current_user.first_name = first_name
    if last_name:
        current_user.last_name = last_name
    if phone:
        current_user.phone = phone
    if job_title:
        current_user.job_title = job_title
    if avatar_url is not None:
        current_user.avatar_url = avatar_url

    db.session.commit()
    record_audit(
        "PROFILE_UPDATE",
        actor=current_user,
        target_type="USER",
        target_id=current_user.id,
        details="Profil utilisateur mis à jour",
        ip=request.remote_addr,
    )
    return jsonify(user=_serialize_me(current_user), message="Profil mis à jour avec succès.")