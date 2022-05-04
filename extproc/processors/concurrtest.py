from json import loads
from typing import Dict, Union

from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from grpc import ServicerContext

from .base import BaseExternalProcessorService


class ConcurrencyTestingService(BaseExternalProcessorService):
    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        callctx.update(
            self.get_headers(
                headers,
                [":path", "x-request-id", "x-gateway-request-id"],
                mapping=["path", "_rid", "grid"],
            )
        )
        response = self.just_continue_headers()
        self.add_header(response.response, "X-Gateway-Request-Id", callctx["grid"])
        return response

    def process_request_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        grid = body.body.decode()
        assert grid == callctx["grid"]

        return self.just_continue_body()

    def process_response_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        data = loads(body.body.decode())
        path = data["path"]
        assert path == callctx["path"]

        response = self.just_continue_body()
        self.add_header(response.response, "X-Gateway-Request-Id", callctx["grid"])
        return response
