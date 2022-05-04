from typing import Dict, List, Optional

from envoy.config.core.v3.base_pb2 import (
    HeaderValueOption as EnvoyHeaderValueOption,
)
from envoy.config.core.v3.base_pb2 import HeaderMap as EnvoyHeaderMap
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
import pytest

from extproc.processors import BaseExternalProcessorService


def assert_empty_header_mutation(headers: ext_api.HeaderMutation) -> None:
    assert isinstance(headers, ext_api.HeaderMutation)
    assert len(headers.set_headers) == 0
    assert len(headers.remove_headers) == 0


def assert_empty_common_response(response: ext_api.CommonResponse) -> None:
    assert isinstance(response, ext_api.CommonResponse)
    assert response.status == ext_api.CommonResponse.ResponseStatus.CONTINUE
    assert_empty_header_mutation(response.header_mutation)


def test_just_continue_response() -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_response()
    assert_empty_common_response(response)


def test_just_continue_headers() -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_headers()
    assert isinstance(response, ext_api.HeadersResponse)
    assert_empty_common_response(response.response)


def test_just_continue_body() -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_body()
    assert isinstance(response, ext_api.BodyResponse)
    assert_empty_common_response(response.response)


def test_just_continue_trailers() -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_trailers()
    assert isinstance(response, ext_api.TrailersResponse)
    assert_empty_header_mutation(response.header_mutation)


@pytest.mark.parametrize(
    "headers, name, result",
    (
        (ext_api.HttpHeaders(), "empty", None),
        (
            ext_api.HttpHeaders(
                headers=EnvoyHeaderMap(
                    headers=[
                        EnvoyHeaderValue(
                            key="empty",
                            value="header",
                        )
                    ]
                )
            ),
            "empty",
            "header",
        ),
        (
            ext_api.HttpHeaders(
                headers=EnvoyHeaderMap(
                    headers=[
                        EnvoyHeaderValue(
                            key="first",
                            value="1",
                        ),
                        EnvoyHeaderValue(
                            key="second",
                            value="2",
                        ),
                    ]
                )
            ),
            "second",
            "2",
        ),
    ),
)
def test_get_header(
    headers: ext_api.HttpHeaders,
    name: str,
    result: Optional[str],
) -> None:
    p = BaseExternalProcessorService()
    value = p.get_header(headers, name)
    assert isinstance(value, str) or value is None
    assert result == value


@pytest.mark.parametrize(
    "headers, names, results",
    (
        (ext_api.HttpHeaders(), ["empty"], {}),
        (
            ext_api.HttpHeaders(
                headers=EnvoyHeaderMap(
                    headers=[
                        EnvoyHeaderValue(
                            key="first",
                            value="1",
                        ),
                        EnvoyHeaderValue(
                            key="second",
                            value="2",
                        ),
                    ]
                )
            ),
            ["second"],
            {"second": "2"},
        ),
        (
            ext_api.HttpHeaders(
                headers=EnvoyHeaderMap(
                    headers=[
                        EnvoyHeaderValue(
                            key="first",
                            value="1",
                        ),
                        EnvoyHeaderValue(
                            key="second",
                            value="2",
                        ),
                    ]
                )
            ),
            ["first", "second"],
            {"first": "1", "second": "2"},
        ),
        (
            ext_api.HttpHeaders(
                headers=EnvoyHeaderMap(
                    headers=[
                        EnvoyHeaderValue(
                            key="first",
                            value="1",
                        ),
                        EnvoyHeaderValue(
                            key="second",
                            value="2",
                        ),
                    ]
                )
            ),
            [
                "empty",
            ],
            {},
        ),
    ),
)
def test_get_headers(
    headers: ext_api.HttpHeaders,
    names: List[str],
    results: Dict[str, str],
) -> None:
    p = BaseExternalProcessorService()
    values = p.get_headers(headers, names)
    assert isinstance(values, dict)
    assert results == values


@pytest.mark.parametrize(
    "key, value",
    (
        ("X-Fake-Header", "value"),
        ("X-Other-Fake-Header", "eulav"),
    ),
)
def test_add_header(key: str, value: str) -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_response()
    assert len(response.header_mutation.set_headers) == 0
    new_header = EnvoyHeaderValueOption(header=EnvoyHeaderValue(key=key, value=value))
    updated = p.add_header(response, key, value)
    assert isinstance(updated, ext_api.CommonResponse)
    assert len(response.header_mutation.set_headers) == 1
    assert new_header in updated.header_mutation.set_headers


@pytest.mark.parametrize(
    "key",
    (
        ("X-Fake-Header"),
        ("X-Other-Fake-Header"),
    ),
)
def test_remove_header(key: str) -> None:
    p = BaseExternalProcessorService()
    response = p.just_continue_response()
    assert len(response.header_mutation.remove_headers) == 0
    updated = p.remove_header(response, key)
    assert isinstance(updated, ext_api.CommonResponse)
    assert len(response.header_mutation.remove_headers) == 1
    assert key in response.header_mutation.remove_headers


@pytest.mark.parametrize(
    "headers",
    (ext_api.HttpHeaders(),),
)
def test_process_request_headers(headers: ext_api.HttpHeaders) -> None:
    p = BaseExternalProcessorService()
    response = p.process_request_headers(headers, None, {})
    assert isinstance(response, ext_api.HeadersResponse)


@pytest.mark.parametrize(
    "headers",
    (ext_api.HttpHeaders(),),
)
def test_process_response_headers(headers: ext_api.HttpHeaders) -> None:
    p = BaseExternalProcessorService()
    response = p.process_response_headers(headers, None, {})
    assert isinstance(response, ext_api.HeadersResponse)


@pytest.mark.parametrize(
    "body",
    (ext_api.HttpBody(),),
)
def test_process_request_body(body: ext_api.HttpBody) -> None:
    p = BaseExternalProcessorService()
    response = p.process_request_body(body, None, {})
    assert isinstance(response, ext_api.BodyResponse)


@pytest.mark.parametrize(
    "body",
    (ext_api.HttpBody(),),
)
def test_process_response_body(body: ext_api.HttpBody) -> None:
    p = BaseExternalProcessorService()
    response = p.process_response_body(body, None, {})
    assert isinstance(response, ext_api.BodyResponse)


@pytest.mark.parametrize(
    "trailers",
    (ext_api.HttpTrailers(),),
)
def test_process_request_trailers(trailers: ext_api.HttpTrailers) -> None:
    p = BaseExternalProcessorService()
    response = p.process_request_trailers(trailers, None, {})
    assert isinstance(response, ext_api.TrailersResponse)


@pytest.mark.parametrize(
    "trailers",
    (ext_api.HttpTrailers(),),
)
def test_process_response_trailers(trailers: ext_api.HttpTrailers) -> None:
    p = BaseExternalProcessorService()
    response = p.process_response_trailers(trailers, None, {})
    assert isinstance(response, ext_api.TrailersResponse)
