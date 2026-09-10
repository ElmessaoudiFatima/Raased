"""
Schémas Pydantic pour l'authentification et l'inscription des managers.
Aligné sur la migration c5909ddd17aa (nouveaux champs users + organizations).
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


# ─────────────────────────────────────────────
# Auth classique
# ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    country: str
    status: str

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    job_title: str | None = None
    phone: str | None = None
    organization_id: uuid.UUID | None = None
    organization: UserOrganizationOut | None = None
    is_active: bool
    email_verified: bool
    account_status: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut



# ─────────────────────────────────────────────
# Inscription manager (formulaire 4 étapes)
# ─────────────────────────────────────────────

class OrganizationInfo(BaseModel):
    """Étape 1 : informations de l'entreprise."""
    name: str
    legal_id: str                       # ICE / RC
    country: str = "Maroc"
    city: str
    phone: str
    address: str
    website: str | None = None
    email: EmailStr                     # email de contact de l'entreprise


class ManagerInfo(BaseModel):
    """Étape 2 : informations du responsable."""
    first_name: str
    last_name: str
    job_title: str
    email: EmailStr                     # email professionnel (recevra l'OTP)
    phone: str
    password: str | None = None
    confirm_password: str | None = None

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v is not None and "password" in info.data and v != info.data["password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


class ManagerRegisterRequest(BaseModel):
    """Corps complet de la requête POST /auth/register."""
    organization: OrganizationInfo
    manager: ManagerInfo


class ManagerRegisterResponse(BaseModel):
    """Réponse après soumission de l'inscription.
    Contient l'ID du manager et de l'organisation pour les étapes suivantes."""
    user_id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    dev_code: str | None = None
    message: str = "Un code de vérification a été envoyé à votre adresse email."


# ─────────────────────────────────────────────
# Vérification OTP & Finalisation inscription (étapes 3 & 4)
# ─────────────────────────────────────────────

class VerifyOTPRequest(BaseModel):
    user_id: uuid.UUID
    code: str


class VerifyOTPResponse(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    email_verified: bool = True
    message: str


class RegisterVerifyRequest(BaseModel):
    user_id: uuid.UUID
    code: str


class RegisterVerifyResponse(BaseModel):
    password_token: str
    user_id: uuid.UUID
    message: str = "E-mail vérifié. Définissez maintenant votre mot de passe."


class RegisterCompleteRequest(BaseModel):
    password_token: str
    password: str
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


class RegisterCompleteResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    message: str = "Compte Raased créé avec succès."


class RegisterResendRequest(BaseModel):
    user_id: uuid.UUID


class RegisterResendResponse(BaseModel):
    dev_code: str | None = None
    message: str = "Un nouveau code de vérification vient d'être envoyé."


class ResendOTPRequest(BaseModel):
    user_id: uuid.UUID



# ─────────────────────────────────────────────
# Documents justificatifs (étape 4 & vue admin)
# ─────────────────────────────────────────────

class OrganizationDocumentOut(BaseModel):
    """Document justificatif d'une organisation."""
    id: uuid.UUID
    organization_id: uuid.UUID
    document_type: str
    file_url: str
    download_url: str | None = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Admin : review des demandes d'inscription
# ─────────────────────────────────────────────

class OrganizationOut(BaseModel):
    """Organisation seule (réponse légère)."""
    id: uuid.UUID
    name: str
    legal_id: str
    country: str
    city: str
    phone: str
    address: str
    website: str | None = None
    email: str
    status: str
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ManagerSummary(BaseModel):
    """Infos du manager associé à une organisation (pour la vue admin)."""
    id: uuid.UUID
    first_name: str
    last_name: str
    job_title: str | None = None
    email: str
    phone: str | None = None
    email_verified: bool

    class Config:
        from_attributes = True


class OrganizationDetailOut(BaseModel):
    """Organisation + manager principal + documents (vue détaillée pour la review admin)."""
    organization: OrganizationOut
    manager: ManagerSummary | None = None
    documents: list[OrganizationDocumentOut] = []


class OrganizationRejectRequest(BaseModel):
    rejection_reason: str


# ─────────────────────────────────────────────
# Manager : création de drivers (invitation)
# ─────────────────────────────────────────────

class DriverCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    # Pas de mot de passe : le driver le définit lui-même via le lien d'invitation


class DriverCreateResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    role: str
    account_status: str
    is_active: bool
    email_verified: bool
    invitation_link: str | None = None
    driver: dict | None = None
    message: str = "Compte conducteur créé et email d'invitation envoyé."

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Driver : activation & définition de mot de passe
# ─────────────────────────────────────────────

class ValidateInvitationResponse(BaseModel):
    valid: bool
    first_name: str
    last_name: str
    email: EmailStr
    role: str = "DRIVER"
    organization_name: str | None = None


class SetPasswordRequest(BaseModel):
    token: str
    password: str
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v