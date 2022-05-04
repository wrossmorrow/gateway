from hashlib import sha256
from typing import Dict, Union

from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from grpc import ServicerContext

from .base import BaseExternalProcessorService


class DigestExternalProcessorService(BaseExternalProcessorService):
    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        callctx.update(
            self.get_headers(
                headers,
                [":path", ":method", "x-gateway-tenant"],
                mapping=["path", "method", "tenant"],
            )
        )

        # add to hash here to assert ordering
        callctx["digest"] = sha256()
        callctx["digest"].update(callctx["tenant"].encode())
        callctx["digest"].update(callctx["method"].encode())
        callctx["digest"].update(callctx["path"].encode())

        response = self.just_continue_headers()

        # GETs don't have bodies
        if callctx["method"].lower() == "get":
            digest = callctx["digest"].hexdigest()
            common_response = response.response
            self.add_header(common_response, "X-Request-Digest", digest)

        return response

    def process_request_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:

        callctx["digest"].update(str(body.body).encode())
        digest = callctx["digest"].hexdigest()

        response = self.just_continue_body()
        common_response = response.response
        self.add_header(common_response, "X-Request-Digest", digest)

        return response
