from random import choice
from string import digits
from uuid import uuid4

from envoy.config.core.v3.base_pb2 import (
    HeaderValueOption as EnvoyHeaderValueOption,
)
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from gateway.cache.v1.cache_pb2 import CachedHeader  # noqa: F401
from gateway.cache.v1.cache_pb2 import CachedRequestResponse
from google.protobuf.timestamp_pb2 import Timestamp
import pytest

from extproc.processors import idempotency

from .conftest import FakeRedisCache

HEX_DIGITS = digits.split() + ["a", "b", "c", "d", "e", "f"]


def random_digest() -> str:
    return "".join(choice(HEX_DIGITS) for i in range(64))


def now_proto() -> Timestamp:
    t = Timestamp()
    t.GetCurrentTime()
    return t


@pytest.mark.parametrize(
    "data",
    [
        CachedRequestResponse(
            key=str(uuid4()),
            path="/api/v0/resource",
            tenant=str(uuid4()),
            identity=str(uuid4()),
            digest=random_digest(),
            when=now_proto(),
            status=choice([0, 200, 201, 401, 403, 409, 500, 504]),
            headers=[],
            body="",
        )
        for i in range(10)
    ],
)
def test_caching_serialization(data: CachedRequestResponse) -> None:

    wire: str = idempotency.serialize_cache_data(data)
    value: CachedRequestResponse = idempotency.deserialize_cache_data(wire)

    assert isinstance(wire, str)
    assert isinstance(value, CachedRequestResponse)
    assert value == data


@pytest.mark.parametrize(
    "data",
    [
        CachedRequestResponse(
            key=str(uuid4()),
            path="/api/v0/resource",
            tenant=str(uuid4()),
            identity=str(uuid4()),
            digest=random_digest(),
            when=now_proto(),
            status=0,  # sentinels must have status == 0
            headers=[],
            body="",
        )
    ],
)
def test_create_sentinel(monkeypatch, data: CachedRequestResponse) -> None:

    cache = FakeRedisCache()
    monkeypatch.setattr(idempotency, "RedisCache", cache)

    p = idempotency.IdempotencyExternalProcessorService()
    p.create_sentinel(data)
    assert cache.exists(data.key)
    assert cache._get(data.key).ttl == idempotency.IDEMP_SENTINEL_TIME
    assert idempotency.deserialize_cache_data(cache.get(data.key)) == data


@pytest.mark.parametrize(
    "data",
    [
        CachedRequestResponse(
            key=str(uuid4()),
            path="/api/v0/resource",
            tenant=str(uuid4()),
            identity=str(uuid4()),
            digest=random_digest(),
            when=now_proto(),
            status=200,  # sentinels must have status == 0
            headers=[],
            body="",
        )
    ],
)
def test_invalid_create_sentinel(monkeypatch, data: CachedRequestResponse) -> None:

    cache = FakeRedisCache()
    monkeypatch.setattr(idempotency, "RedisCache", cache)

    p = idempotency.IdempotencyExternalProcessorService()
    with pytest.raises(ValueError):
        p.create_sentinel(data)


@pytest.mark.parametrize(
    "data",
    [
        CachedRequestResponse(
            key=str(uuid4()),
            path="/api/v0/resource",
            tenant=str(uuid4()),
            identity=str(uuid4()),
            digest=random_digest(),
            when=now_proto(),
            status=choice([200, 201, 401, 403, 409, 500, 504]),
            headers=[],
            body="",
        ),
    ],
)
def test_cache_response(monkeypatch, data: CachedRequestResponse) -> None:

    cache = FakeRedisCache()
    monkeypatch.setattr(idempotency, "RedisCache", cache)

    p = idempotency.IdempotencyExternalProcessorService()
    p.cache_response(data)
    assert cache.exists(data.key)
    assert cache._get(data.key).ttl == idempotency.IDEMP_CACHE_TIME
    assert idempotency.deserialize_cache_data(cache.get(data.key)) == data


@pytest.mark.parametrize(
    "data",
    [
        CachedRequestResponse(
            key=str(uuid4()),
            path="/api/v0/resource",
            tenant=str(uuid4()),
            identity=str(uuid4()),
            digest=random_digest(),
            when=now_proto(),
            status=choice([200, 201, 401, 403, 409, 500, 504]),
            headers=[],
            body="",
        ),
    ],
)
def test_respond_from_cache(monkeypatch, data: CachedRequestResponse) -> None:

    cache = FakeRedisCache()
    monkeypatch.setattr(idempotency, "RedisCache", cache)

    p = idempotency.IdempotencyExternalProcessorService()

    # raise a ValueError when asked for a response from cached
    with pytest.raises(ValueError):
        p.response_from_cache(data.key)

    # cache the data and assert construction of response
    p.cache_response(data)
    response = p.response_from_cache(data.key)

    assert isinstance(response, ext_api.ImmediateResponse)

    cached_header = EnvoyHeaderValueOption(
        header=EnvoyHeaderValue(key="X-Gateway-Cached", value="true")
    )
    assert cached_header in response.headers.set_headers
