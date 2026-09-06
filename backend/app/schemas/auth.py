import uuid
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    organization_id: uuid.UUID | None
    is_active: bool

    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    name: str


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str

    class Config:
        from_attributes = True


class ManagerCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    organization_id: uuid.UUID


class DriverCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    # pas d'organization_id ici : imposé automatiquement = celle du manager connecté