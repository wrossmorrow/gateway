from uuid import uuid4

from envoy.config.core.v3.base_pb2 import (
    HeaderValueOption as EnvoyHeaderValueOption,
)
from envoy.config.core.v3.base_pb2 import HeaderMap as EnvoyHeaderMap
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
import pytest

from extproc.processors import ConcurrencyTestingService


@pytest.mark.parametrize(
    "headers",
    (
        ext_api.HttpHeaders(
            headers=EnvoyHeaderMap(
                headers=[
                    EnvoyHeaderValue(
                        key=":path",
                        value="/api/v0/resource",
                    ),
                    EnvoyHeaderValue(
                        key="x-request-id",
                        value=str(uuid4()),
                    ),
                    EnvoyHeaderValue(
                        key="x-gateway-request-id",
                        value=str(uuid4()),
                    ),
                ]
            )
        ),
    ),
)
def test_process_request_headers(headers: ext_api.HttpHeaders) -> None:

    ctx = {}

    p = ConcurrencyTestingService()
    response = p.process_request_headers(headers, None, ctx)
    assert isinstance(response, ext_api.HeadersResponse)
    for k in ["path", "_rid", "grid"]:
        assert k in ctx

    key = "X-Gateway-Request-Id"
    value = ctx["grid"]
    new_header = EnvoyHeaderValueOption(header=EnvoyHeaderValue(key=key, value=value))
    assert len(response.response.header_mutation.set_headers) == 1
    assert new_header in response.response.header_mutation.set_headers
