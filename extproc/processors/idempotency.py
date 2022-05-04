from base64 import b64decode, b64encode
from datetime import timedelta as td
from json import dumps
from logging import getLogger
from typing import Dict, Union

from envoy.config.core.v3.base_pb2 import (
    HeaderValueOption as EnvoyHeaderValueOption,
)
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from envoy.type.v3.http_status_pb2 import HttpStatus as EnvoyHttpStatus
from envoy.type.v3.http_status_pb2 import StatusCode as EnvoyStatusCode
from gateway.cache.v1.cache_pb2 import CachedHeader, CachedRequestResponse
from google.protobuf.json_format import MessageToJson
from grpc import ServicerContext

from ..utils.redis import RedisCache
from .base import BaseExternalProcessorService

logger = getLogger(__name__)

# TODO: make configurable
IDEMP_CACHE_TIME = td(hours=24)
IDEMP_SENTINEL_TIME = td(minutes=3)

# envoy/HTTP uppercases method names
IDEMP_METHODS = ["POST"]


class IdempotencyExternalProcessorService(BaseExternalProcessorService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = RedisCache()

    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        values = self.get_headers(
            headers,
            [":method", ":path", "x-gateway-tenant", "x-request-digest", "x-idempotency-key"],
            mapping=["method", "path", "tenant", "digest", "idemp_key"],
        )

        # use only on certain methods
        if values["method"] not in IDEMP_METHODS:
            logger.debug(f"skipping idempotency on {values['method']} {values['path']}")
            callctx["cached"] = None  # flag, filter not needed on request
            return self.just_continue_headers()

        logger.debug(f"processing idempotency on {values['method']} {values['path']}")

        # default the idempotency key
        if values.get("idemp_key") is None:
            logger.debug("defaulting key to request's digest")
            values["idemp_key"] = values["digest"]

        # respond if cached
        if self.cache.exists(values["idemp_key"]):
            return self.response_from_cache(values["idemp_key"])

        # o/w, start the cache value here
        callctx["cached"] = CachedRequestResponse(
            key=values["idemp_key"],
            path=values["path"],
            tenant=values["tenant"],
            digest=values["digest"],
        )
        callctx["cached"].when.GetCurrentTime()

        self.create_sentinel(callctx["cached"])

        return self.just_continue_headers()

    def process_response_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        cached = callctx["cached"]
        if cached is None:
            return self.just_continue_headers()

        self.delete_sentinel(cached.key)
        # NOTE: between now and the actual cache time is the "danger
        # zone". We have a response, because we have response headers,
        # but we haven't cached it yet so we can't respond with it
        # if we got another request. Moreover, because we _have_ a
        # response we have processed the request and we can't keep
        # the sentinel or we risk losing the response forever if the
        # cache update below fails.

        for header in headers.headers.headers:
            if header.key[0] != ":":
                cached.headers.append(CachedHeader(key=header.key, value=header.value))
            elif header.key == ":status":
                cached.status = int(str(header.value))

        response = self.just_continue_headers()
        self.add_header(response.response, "X-Gateway-Cached", "false")
        return response

    def process_response_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:

        cached = callctx["cached"]
        if cached is None:
            return self.just_continue_body()

        # cache the response now that we have the body, if request
        # was successful
        if cached.status in [200, 201]:
            cached.body = body.body
            self.cache_response(cached)

        return self.just_continue_body()

    # cache wrappers

    def create_sentinel(self, data: CachedRequestResponse):
        if data.status != 0:
            raise ValueError(f"Sentinels must have status == 0 (not {data.status})")
        self.cache.setex(data.key, serialize_cache_data(data), expiry=IDEMP_SENTINEL_TIME)

    def delete_sentinel(self, key: str):
        if self.cache.exists(key):
            data = self.cache.get(key)
            cached = deserialize_cache_data(data)
            if cached.status == 0:
                self.cache.delete(key)
            # if status is not 0, ignore (not a sentinel)

    def cache_response(self, data: CachedRequestResponse) -> None:
        self.cache.setex(
            data.key,
            serialize_cache_data(data),
            expiry=IDEMP_CACHE_TIME,
        )

    def response_from_cache(self, key: str) -> ext_api.ImmediateResponse:

        data = self.cache.get(key)
        if data is None:
            raise ValueError(f"{key} is not cached")

        cached = deserialize_cache_data(data)

        if cached.status == 0:  # this is a sentinel, respond 409
            return ext_api.ImmediateResponse(
                status=EnvoyHttpStatus(code=EnvoyStatusCode.Conflict),
                headers=ext_api.HeaderMutation(),
                body=dumps(
                    {
                        "message": "Duplicate request in progress",
                        "status": 409,
                        "details": MessageToJson(cached, indent=0),
                    }
                ),
                details=MessageToJson(cached, indent=0),
            )

        response_headers = ext_api.HeaderMutation()
        for header in cached.headers:
            response_headers.set_headers.append(
                EnvoyHeaderValueOption(header=EnvoyHeaderValue(key=header.key, value=header.value))
            )
        response_headers.set_headers.append(
            EnvoyHeaderValueOption(header=EnvoyHeaderValue(key="X-Gateway-Cached", value="true"))
        )

        return ext_api.ImmediateResponse(
            status=EnvoyHttpStatus(code=cached.status),
            headers=response_headers,
            body=cached.body,
        )


# non-class helpers


def serialize_cache_data(data: CachedRequestResponse) -> str:
    return b64encode(data.SerializeToString()).decode()


def deserialize_cache_data(data: str) -> CachedRequestResponse:
    obj = CachedRequestResponse()
    obj.ParseFromString(b64decode(data.encode()))
    return obj
