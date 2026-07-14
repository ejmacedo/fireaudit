import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterIndividualPayload(BaseModel):
    account_type: Literal["individual"]
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=1, max_length=200)


class RegisterMultiempresaPayload(BaseModel):
    account_type: Literal["multiempresa"]
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tax_id: str = Field(min_length=1, max_length=64)


RegisterPayload = Annotated[
    RegisterIndividualPayload | RegisterMultiempresaPayload,
    Field(discriminator="account_type"),
]


class RegisterResponse(BaseModel):
    account_id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshPayload(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutPayload(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
