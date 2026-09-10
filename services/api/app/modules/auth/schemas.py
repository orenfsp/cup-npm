from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from app.db.models.enums import StaffRole


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=1024)


class StaffProfile(BaseModel):
    id: UUID
    login: str
    display_name: str
    role: StaffRole
    must_change_password: bool


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    staff: StaffProfile


class LogoutResponse(BaseModel):
    status: str = "ok"


class ChangePasswordRequest(BaseModel):
    password: SecretStr = Field(min_length=12, max_length=200)


class ChangePasswordResponse(BaseModel):
    status: str = "password_changed"
