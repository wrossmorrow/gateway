import re
from uuid import uuid4

from envoy.config.core.v3.base_pb2 import HeaderMap as EnvoyHeaderMap
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
import pytest

from extproc.processors import DigestExternalProcessorService


@pytest.mark.parametrize(
    "headers",
    (
        ext_api.HttpHeaders(
            headers=EnvoyHeaderMap(
                headers=[
                    EnvoyHeaderValue(
                        key=":method",
                        value="get",
                    ),
                    EnvoyHeaderValue(
                        key=":path",
                        value="/api/v0/resource",
                    ),
                    EnvoyHeaderValue(
                        key="x-gateway-tenant",
                        value=str(uuid4()),
                    ),
                ]
            )
        ),
    ),
)
@pytest.mark.parametrize(
    "body",
    (ext_api.HttpBody(),),
)
def test_digester_flow(headers: ext_api.HttpHeaders, body: ext_api.HttpBody) -> None:

    ctx = {}

    p = DigestExternalProcessorService()
    response = p.process_request_headers(headers, None, ctx)
    assert isinstance(response, ext_api.HeadersResponse)
    for k in ["tenant", "method", "path", "digest"]:
        assert k in ctx

    response = p.process_request_body(body, None, ctx)

    key = "X-Request-Digest"
    digest = None
    for h in response.response.header_mutation.set_headers:
        if h.header.key == key:
            digest = h.header.value
    assert digest is not None
    assert re.match(r"^[0-9a-f]{64}$", digest) is not None
