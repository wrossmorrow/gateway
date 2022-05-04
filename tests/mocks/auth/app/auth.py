from base64 import b64decode, b64encode, urlsafe_b64decode
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import Header

from .crud import compute_hmac, get_db, get_key_in_db
from .errors import Forbidden, NotFound, Unauthorized
from .models import IdentityAndScope, TokenIdentity, TokenScope
from .tokens import verify


def authorize(
    scopes: List[TokenScope],
    required: TokenScope,
) -> None:
    if required not in scopes:
        raise Forbidden()


def authenticate(
    identity: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    x_api_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> IdentityAndScope:

    if x_api_token is not None:
        return authenticate_with_api_token(x_api_token)

    if authorization is not None:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ")[1]
            return authenticate_with_api_token(token)
        if authorization.lower().startswith("basic "):
            identity, secret = decode_basic_auth_header(authorization.split(" ")[1])
            return authenticate_with_api_key(identity, secret)
        if identity is not None:
            return authenticate_with_api_key(identity, authorization)

    if (identity is not None) and (x_api_key is not None):
        return authenticate_with_api_key(identity, authorization)

    raise Unauthorized()


def decode_basic_auth_header(creds: str) -> Tuple[str, str]:
    return urlsafe_b64decode(creds.encode()).decode().split(":")


def authenticate_with_api_token(token: str) -> IdentityAndScope:
    claims = verify(token)
    return IdentityAndScope(identity=claims.identity, scopes=claims.scopes)


def authenticate_with_api_key(identity: str, secret: str) -> IdentityAndScope:

    _id: UUID
    _pk: bytes

    try:
        _id = UUID(identity)
    except (TypeError, ValueError) as err:
        raise Unauthorized() from err

    try:
        _pk = b64decode(secret.encode())
    except (TypeError, ValueError) as err:
        raise Unauthorized() from err

    for db in get_db():
        try:
            key = get_key_in_db(db, _id)
        except NotFound:
            raise Unauthorized()
        _st = b64decode(key.salt.encode())
        hmac, _ = compute_hmac(_id.bytes, _pk, salt=_st)
        hmac = b64encode(hmac).decode()
        if hmac == key.hmac:
            return IdentityAndScope(
                identity=TokenIdentity(tenant=key.tenant, key_id=key.key_id, user_id=key.user_id),
                scopes=[
                    TokenScope(resource=scope["resource"], action=scope["action"])
                    for scope in key.scopes
                ],
            )

    raise Unauthorized()
