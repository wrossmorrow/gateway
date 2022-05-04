from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from json import dumps
from logging import getLogger
from os import environ
import re
from typing import Dict, List, Optional, Tuple, Union

from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from envoy.type.v3.http_status_pb2 import HttpStatus, StatusCode
from google.protobuf.timestamp_pb2 import Timestamp
from grpc import ServicerContext
import jwt
import requests

from .base import BaseExternalProcessorService

logger = getLogger(__name__)

AUTH_HOST = environ.get("AUTH_HOST", "http://auth")
AUTH_PORT = int(environ.get("AUTH_PORT", "443"))
AUTH_URL = f"{AUTH_HOST}:{AUTH_PORT}/api/v0/tokens"

# match the service settings
TOKEN_PUBLIC_KEY = environ.get("TOKEN_PUBLIC_KEY", "CHANGE_ME_PLEASE")
TOKEN_PRIVATE_KEY = environ.get("TOKEN_PRIVATE_KEY", "CHANGE_ME_PLEASE")
TOKEN_ALGORITHM = environ.get("TOKEN_ALGORITHM", "HS256")
TOKEN_ISSUER = environ.get("TOKEN_ISSUER", "auth")
TOKEN_AUDIENCE = environ.get("TOKEN_AUDIENCE", "auth")


PATH_REGEX = re.compile(r"/(api|docs|test)/v(([0-9]+)(\.[0-9]+)?)/(/.*)?$")
# Groups:
#
#   1: "subdomain"
#   2: full version
#   3: major version
#   4: minor version
#   5: path
#
PATH_PARAM_PLACEHOLDER = ":"
UUID_REGEX = re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}")
PATH_PARAM_PATTERNS = [UUID_REGEX]  # add other path param styles IYI


WHITELIST = ["/health"]


@dataclass
class HeaderInfo:
    identity: Optional[str] = None
    authorization: Optional[str] = None
    secret: Optional[str] = None
    token: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None


@dataclass
class APICall:
    version: str
    endpoint: str
    method: str


class Unauthenticated(Exception):
    pass


class NoCredentials(Unauthenticated):
    pass


class MalformedCredentials(Unauthenticated):
    pass


class MalformedURL(Exception):
    pass


class AuthnExternalProcessorService(BaseExternalProcessorService):
    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        response = self.just_continue_headers()
        common_response = response.response

        # add a "request started" header
        started = Timestamp()
        started.GetCurrentTime()
        self.add_header(common_response, "X-Request-Started", started.ToJsonString())

        info = extract_header_info(headers.headers.headers)

        try:

            if info.token is None:
                info.token = verify_basic_auth(info.identity, info.secret)

            claims = verify_token(info.token)
            encoded_claims = urlsafe_b64encode(dumps(claims).encode())

            if info.identity:
                self.add_header(common_response, "X-Gateway-KeyId", claims["identity"]["key_id"])
            self.add_header(common_response, "X-Gateway-Tenant", claims["identity"]["tenant"])
            self.add_header(common_response, "X-Gateway-UserId", claims["identity"]["user_id"])
            self.add_header(common_response, "X-Auth-Claims", encoded_claims)
            return response

        except Unauthenticated as err:
            return ext_api.ImmediateResponse(
                status=HttpStatus(code=StatusCode.Unauthorized),
                headers=ext_api.HeaderMutation(),
                body=dumps(
                    {
                        "message": "Unauthenticated",
                        "status": 401,
                        "details": f"{err.__class__.__name__} {err}",
                    }
                ),
                details=f"{err.__class__.__name__} {err}",
            )

        except Exception as err:  # TODO: tighten error
            return ext_api.ImmediateResponse(
                status=HttpStatus(code=StatusCode.InternalServerError),
                headers=ext_api.HeaderMutation(),
                body=dumps(
                    {
                        "message": "ServerError",
                        "status": 500,
                        "details": f"{err.__class__.__name__} {err}",
                    }
                ),
                details=f"{err.__class__.__name__} {err}",
            )

        return self.just_continue_headers()


def extract_header_info(headers: List[EnvoyHeaderValue]) -> HeaderInfo:

    info = HeaderInfo()

    for header in headers:
        if header.key == ":method":
            info.method = str(header.value)
        elif header.key == ":path":
            info.path = str(header.value)
        elif header.key == "identity":
            info.identity = str(header.value)
        elif header.key == "authorization":
            info.authorization = str(header.value)
        elif header.key == "x-api-key":
            info.secret = str(header.value)
        elif header.key == "x-api-token":
            info.token = str(header.value)

    if info.authorization is not None:
        if info.authorization.lower().startswith("bearer "):
            info.token = info.authorization.split(" ")[1]
        elif info.authorization.lower().startswith("basic "):
            creds = info.authorization.split(" ")[1]
            info.identity, info.secret = decode_basic_auth_header(creds)
        else:
            info.secret = info.authorization

    return info


def decode_basic_auth_header(creds: str) -> Tuple[str, str]:
    return urlsafe_b64decode(creds.encode()).decode().split(":")


def verify_basic_auth(identity: str, secret: str) -> str:
    """Call auth service with API key (identity and secret)"""

    if (identity is None) or (secret is None):
        raise NoCredentials("One of identity or secret not passed")
    if not UUID_REGEX.match(identity):
        raise MalformedCredentials("Identity is not a UUID")

    # TODO: handle initial connection error (not a response error)
    # TODO: probably want retries
    basic = urlsafe_b64encode(f"{identity}:{secret}".encode()).decode()
    headers = {"Authorization": f"Basic {basic}"}
    response = requests.get(AUTH_URL, headers=headers)
    if response.status_code in [200, 201]:
        return response.json()["token"]
    elif response.status_code < 500:
        raise Unauthenticated(f"{response.text}")
    response.raise_for_status()


def verify_token(token: str) -> Dict:
    try:
        return jwt.decode(
            token,
            TOKEN_PUBLIC_KEY,
            algorithms=["HS256"],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
        )
    except (
        jwt.exceptions.ExpiredSignatureError,
        jwt.exceptions.InvalidSignatureError,
        jwt.exceptions.InvalidIssuerError,
        jwt.exceptions.InvalidAudienceError,
        jwt.exceptions.InvalidIssuedAtError,
        jwt.exceptions.ImmatureSignatureError,
        jwt.exceptions.MissingRequiredClaimError,
        jwt.exceptions.DecodeError,
        jwt.exceptions.InvalidTokenError,
    ) as err:
        raise Unauthenticated() from err
