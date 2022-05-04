from fastapi import HTTPException


class NotFound(HTTPException):
    def __init__(self, *args, **kwargs):
        kwargs["status_code"] = 404
        super().__init__(*args, **kwargs)


class Unauthorized(HTTPException):
    def __init__(self, *args, **kwargs):
        kwargs["status_code"] = 401
        super().__init__(*args, **kwargs)


class Forbidden(HTTPException):
    def __init__(self, *args, **kwargs):
        kwargs["status_code"] = 403
        super().__init__(*args, **kwargs)


class ServerError(HTTPException):
    def __init__(self, *args, **kwargs):
        kwargs["status_code"] = 500
        super().__init__(*args, **kwargs)


class InvalidAlgorithmError(Exception):
    pass


class TokenExpiredError(Unauthorized):
    pass


class InvalidSignatureError(Unauthorized):
    pass


class InvalidIssuerError(Unauthorized):
    pass


class InvalidAudienceError(Unauthorized):
    pass


class InvalidIssuedAtError(Unauthorized):
    pass


class ImmatureSignatureError(Unauthorized):
    pass


class MissingRequiredClaimError(Unauthorized):
    pass
