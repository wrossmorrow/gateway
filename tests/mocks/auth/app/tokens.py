from datetime import datetime as dt
from datetime import timezone as tz
from json import loads
from os import environ
from typing import List, Optional
from uuid import uuid4

import jwt

from .errors import (
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuedAtError,
    InvalidIssuerError,
    InvalidSignatureError,
    MissingRequiredClaimError,
    ServerError,
    TokenExpiredError,
    Unauthorized,
)
from .models import TokenClaims, TokenIdentity, TokenScope

TOKEN_PUBLIC_KEY = environ.get("TOKEN_PUBLIC_KEY", "CHANGE_ME_PLEASE")
TOKEN_PRIVATE_KEY = environ.get("TOKEN_PRIVATE_KEY", "CHANGE_ME_PLEASE")
TOKEN_ALGORITHM = environ.get("TOKEN_ALGORITHM", "HS256")
TOKEN_ISSUER = environ.get("TOKEN_ISSUER", "auth")
TOKEN_AUDIENCE = environ.get("TOKEN_AUDIENCE", "auth")
TOKEN_TTL = int(environ.get("TOKEN_TTL", "300"))


def encode(
    identity: TokenIdentity,
    scopes: List[TokenScope],
    iss: Optional[str] = TOKEN_ISSUER,
    aud: Optional[str] = TOKEN_AUDIENCE,
    alg: Optional[str] = TOKEN_ALGORITHM,
    nbf: Optional[int] = None,
    jti: Optional[str] = None,
    ttl: Optional[int] = TOKEN_TTL,
) -> str:
    """
    encode claims into a JWT using passed data,
    defaulting to settings imported from environment
    """
    iat = int(dt.now(tz.utc).timestamp())
    nbf = iat if nbf is None else max(iat, nbf)
    exp = nbf + ttl
    claims = TokenClaims(
        exp=exp,  # max(nbf, iat) + ttl
        nbf=nbf,  # max(nbf, iat)
        iat=iat,  # always now
        iss=iss,
        aud=aud,
        sub=str(identity.user_id),
        jti=jti if jti else str(uuid4()),
        identity=identity,
        scopes=scopes,
        # scopes = ...
    )
    try:
        return jwt.encode(
            loads(claims.json()),  # this is awful, but serializes types
            TOKEN_PRIVATE_KEY,
            algorithm=TOKEN_ALGORITHM,
        )
    except NotImplementedError as err:
        # Raised when the specified algorithm is not recognized by PyJWT
        raise InvalidAlgorithmError() from err


def verify(
    token: str,
    iss: Optional[str] = None,
    aud: Optional[str] = None,
    key: Optional[str] = None,
    alg: Optional[str] = None,
) -> TokenClaims:
    """
    decode claims from a JWT using passed data,
    defaulting to settings defined in config.py
    """
    try:
        claims = jwt.decode(
            token,
            TOKEN_PUBLIC_KEY,
            algorithms=[TOKEN_ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
        )
        return TokenClaims(
            iss=claims["iss"],
            sub=claims["sub"] if "sub" in claims else None,
            aud=claims["aud"],
            exp=int(claims["exp"]),
            nbf=int(claims["nbf"]),
            iat=int(claims["iat"]),
            jti=claims["jti"] if "jti" in claims else None,
            identity=TokenIdentity(**claims["identity"]),
            scopes=[TokenScope(**scope) for scope in claims["scopes"]],
        )

    except jwt.exceptions.ExpiredSignatureError as err:
        # Raised when a token’s exp claim indicates that it has expired
        raise TokenExpiredError() from err

    except jwt.exceptions.InvalidSignatureError as err:
        # Raised when a token’s signature doesn’t match the one provided
        # as part of the token.
        raise InvalidSignatureError() from err

    except jwt.exceptions.InvalidIssuerError as err:
        # Raised when a token’s iss claim does not match the expected issuer
        raise InvalidIssuerError() from err

    except jwt.exceptions.InvalidAudienceError as err:
        # Raised when a token’s aud claim does not match one of the expected
        # audience values
        raise InvalidAudienceError() from err

    except jwt.exceptions.InvalidIssuedAtError as err:
        # Raised when a token’s iat claim is in the future
        raise InvalidIssuedAtError() from err

    except jwt.exceptions.ImmatureSignatureError as err:
        # Raised when a token’s nbf claim represents a time in the future
        raise ImmatureSignatureError() from err

    except jwt.exceptions.MissingRequiredClaimError as err:
        # Raised when a claim that is required to be present is not contained
        # in the claimset
        raise MissingRequiredClaimError() from err

    except (
        jwt.exceptions.DecodeError,
        jwt.exceptions.InvalidTokenError,
    ) as err:
        raise Unauthorized() from err

    except (
        jwt.exceptions.InvalidKeyError,
        jwt.exceptions.InvalidAlgorithmError,
    ) as err:
        # Raised when the specified key is not in the proper format
        # Raised when the specified algorithm is not recognized by PyJWT
        raise ServerError() from err
