from datetime import datetime as dt
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class TokenIdentity(BaseModel):
    tenant: UUID
    user_id: UUID
    key_id: UUID


class AllowedAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    WRITE = "write"  # == CREATE, UPDATE, & DELETE


class TokenScope(BaseModel):
    resource: str
    action: AllowedAction


class IdentityAndScope(BaseModel):
    identity: TokenIdentity
    scopes: List[TokenScope]


class TokenClaims(BaseModel):
    iat: int
    nbf: int
    exp: int
    iss: str
    sub: str
    aud: str
    jti: str
    identity: TokenIdentity
    scopes: List[TokenScope]


class TokenCreated(BaseModel):
    token: str


class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class APIKeyModel(BaseModel):
    tenant: Optional[UUID] = None
    user_id: Optional[str] = None
    key_id: Optional[UUID] = None
    created_at: Optional[dt] = None
    updated_at: Optional[dt] = None
    revoked_at: Optional[dt] = None
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    scopes: List[TokenScope]

    class Config:
        orm_mode = True
        use_enum_values = True


class APIKeyModelCreated(APIKeyModel):
    secret: str = None

    class Config:
        orm_mode = True
