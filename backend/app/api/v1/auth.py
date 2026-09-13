from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, create_password_token
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    ManagerRegisterRequest,
    ManagerRegisterResponse,
    MeResponse,
    OrganizationDocumentOut,
    RegisterCompleteRequest,
    RegisterCompleteResponse,
    RegisterResendRequest,
    RegisterResendResponse,
    RegisterVerifyRequest,
    RegisterVerifyResponse,
    ResendOTPRequest,
    SetPasswordRequest,
    TokenResponse,
    UserOut,
    ValidateInvitationResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.services.auth_service import (
    authenticate_user,
    complete_manager_registration,
    register_manager,
    resend_otp,
    set_driver_password,
    validate_invitation_token,
    verify_otp,
)
from app.services.document_service import save_organization_document
from app.services.email_service import send_otp_email
from app.api.deps import get_current_user
from app.db.models.users import User

router = APIRouter(prefix="/auth", tags=["auth"])



# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and generate access token",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user using email and password.
    Returns a JWT bearer access token upon successful authentication.
    """
    user = await authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or email not verified.",
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "organization_id": str(user.organization_id) if user.organization_id else None,
    })
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user,
    )



# ─────────────────────────────────────────────
# Inscription manager (self-service)
# ─────────────────────────────────────────────

@router.post(
    "/register",
    response_model=ManagerRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register manager and organization (Steps 1 & 2)",
)
async def register(payload: ManagerRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Creates the organization (status=PENDING) and manager account,
    then sends a verification OTP to the manager's email address.
    """
    manager, otp_code = await register_manager(db, payload)

    send_otp_email(
        to_email=manager.email,
        otp_code=otp_code,
        first_name=manager.first_name,
    )

    settings = get_settings()
    dev_code = otp_code if not settings.SMTP_HOST else None

    return ManagerRegisterResponse(
        user_id=manager.id,
        organization_id=manager.organization_id,
        email=manager.email,
        dev_code=dev_code,
    )


# ─────────────────────────────────────────────
# Vérification OTP & Finalisation (étapes 3 & 4)
# ─────────────────────────────────────────────

@router.post(
    "/register/verify",
    response_model=RegisterVerifyResponse,
    summary="Verify registration OTP and get password token (Step 3)",
)
async def register_verify(
    payload: RegisterVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the 6-digit OTP code received by email for a new registration.
    Returns a short-lived password_token to authorize setting the password.
    """
    success, message, org_id = await verify_otp(db, payload.user_id, payload.code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    password_token = create_password_token(payload.user_id)
    return RegisterVerifyResponse(
        password_token=password_token,
        user_id=payload.user_id,
        message="Email verified. You can now set your password.",
    )


@router.post(
    "/register/complete",
    response_model=RegisterCompleteResponse,
    summary="Complete registration by setting password (Step 4)",
)
async def register_complete(
    payload: RegisterCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the password_token, sets the manager's password,
    activates the user account (account_status='ACTIVE'),
    and returns a valid JWT access token for immediate session creation.
    """
    user = await complete_manager_registration(db, payload.password_token, payload.password)
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "organization_id": str(user.organization_id) if user.organization_id else None,
    })
    return RegisterCompleteResponse(
        access_token=token,
        token_type="bearer",
        user=user,
        message="Raased account created successfully.",
    )


@router.post(
    "/register/resend",
    response_model=RegisterResendResponse,
    summary="Resend registration verification OTP",
)
async def register_resend(
    payload: RegisterResendRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates and sends a new verification OTP code for manager registration.
    """
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == payload.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    otp_code, message = await resend_otp(db, payload.user_id)
    if otp_code is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    send_otp_email(
        to_email=user.email,
        otp_code=otp_code,
        first_name=user.first_name,
    )
    settings = get_settings()
    dev_code = otp_code if not settings.SMTP_HOST else None
    return RegisterResendResponse(
        dev_code=dev_code,
        message=message,
    )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    summary="Verify email OTP code (Step 3 - direct)",
)
async def verify_email_otp(
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the 6-digit OTP code received by email.
    Marks the manager's email as verified.
    """
    success, message, org_id = await verify_otp(db, payload.user_id, payload.code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return VerifyOTPResponse(
        user_id=payload.user_id,
        organization_id=org_id,
        email_verified=True,
        message=message,
    )


# ─────────────────────────────────────────────
# Téléversement de documents (étape 5)
# ─────────────────────────────────────────────

@router.post(
    "/organizations/{org_id}/documents",
    response_model=list[OrganizationDocumentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Upload organization and manager verification documents (Step 5)",
)
async def upload_documents(
    org_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload optional supporting verification documents (PDF, JPG, PNG up to 10 MB each).
    Step 5 of the manager self-registration process.
    Accepts COMPANY_CERTIFICATE and RESPONSIBLE_ID files.
    """
    form = await request.form()
    saved_docs = []

    company_cert = form.get("COMPANY_CERTIFICATE") or form.get("company_certificate")
    if company_cert and hasattr(company_cert, "filename") and company_cert.filename:
        doc = await save_organization_document(
            db=db,
            organization_id=org_id,
            document_type="COMPANY_CERTIFICATE",
            file=company_cert,
        )
        saved_docs.append(
            OrganizationDocumentOut(
                id=doc.id,
                organization_id=doc.organization_id,
                document_type=doc.document_type,
                file_url=doc.file_url,
                download_url=f"/api/v1/admin/documents/{doc.id}/download",
                uploaded_at=doc.uploaded_at,
            )
        )

    resp_id = form.get("RESPONSIBLE_ID") or form.get("responsible_id")
    if resp_id and hasattr(resp_id, "filename") and resp_id.filename:
        doc = await save_organization_document(
            db=db,
            organization_id=org_id,
            document_type="RESPONSIBLE_ID",
            file=resp_id,
        )
        saved_docs.append(
            OrganizationDocumentOut(
                id=doc.id,
                organization_id=doc.organization_id,
                document_type=doc.document_type,
                file_url=doc.file_url,
                download_url=f"/api/v1/admin/documents/{doc.id}/download",
                uploaded_at=doc.uploaded_at,
            )
        )

    return saved_docs


# ─────────────────────────────────────────────
# Renvoi OTP (générique)
# ─────────────────────────────────────────────

@router.post(
    "/resend-otp",
    summary="Resend email verification OTP code",
)
async def resend_email_otp(
    payload: ResendOTPRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates and sends a new verification OTP code to the manager's email address.
    """
    from app.db.models.users import User
    from sqlalchemy import select

    # Récupérer le prénom pour l'email
    result = await db.execute(select(User).where(User.id == payload.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    otp_code, message = await resend_otp(db, payload.user_id)

    if otp_code is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    send_otp_email(
        to_email=user.email,
        otp_code=otp_code,
        first_name=user.first_name,
    )
    return {"message": message}


# ─────────────────────────────────────────────
# Profil utilisateur courant
# ─────────────────────────────────────────────

@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current authenticated user profile",
)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """
    Returns the profile information of the currently authenticated user.
    """
    return MeResponse(user=current_user)



# ─────────────────────────────────────────────
# Invitation et activation compte Driver
# ─────────────────────────────────────────────

@router.get(
    "/invitations/validate",
    response_model=ValidateInvitationResponse,
    summary="Validate driver invitation token",
)
async def validate_invitation(
    token: str = Query(..., description="Invitation token received via email link"),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates a driver's invitation token before displaying the set-password form.
    Returns user info and organization name.
    """
    user, org = await validate_invitation_token(db, token)
    return ValidateInvitationResponse(
        valid=True,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role,
        organization_name=org.name if org else None,
    )


@router.post(
    "/invitations/accept",
    summary="Set password and activate invited driver account (frontend route)",
)
@router.post(
    "/set-password",
    summary="Set password and activate invited driver account",
)
async def set_password(
    payload: SetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the invitation token, sets the driver's password,
    activates the account (account_status='ACTIVE', email_verified=True),
    and marks the invitation token as used.
    """
    await set_driver_password(db, payload.token, payload.password)
    return {
        "message": "Password set successfully. Your account is now active and you can sign in."
    }