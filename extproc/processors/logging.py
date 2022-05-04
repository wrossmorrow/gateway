from json import JSONDecodeError, loads
from logging import getLogger
from typing import Dict, List, Union

from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from flatten_json import flatten
from gateway.log.v1 import log_pb2 as api
from grpc import ServicerContext

from ..utils.kafka import kafka_config, KAFKA_TOPIC, ProtobufProducer
from .base import BaseExternalProcessorService

logger = getLogger(__name__)


class LoggingExternalProcessorService(BaseExternalProcessorService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # chain initialization upwards
        self._producer = ProtobufProducer(**kafka_config())

    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        # start the log
        log = api.Log(
            record=api.LogRecord(),
            identity=api.LogIdentity(),
        )

        callctx["content_type"] = "text/plain"

        # we loop here because we store all the data
        for header in headers.headers.headers:

            if header.key == ":method":
                log.record.method = str(header.value)
            elif header.key == ":path":
                log.record.path = str(header.value)
            elif header.key == ":authority":
                log.record.domain = str(header.value)
            elif header.key == ":scheme":
                log.record.url = str(header.value)  # just start here, see below
            elif header.key == "x-request-started":
                log.record.start_time.FromJsonString(str(header.value))
            elif header.key == "x-request-id":
                log.record.request_id = str(header.value)
            elif header.key == "x-gateway-tenant":
                log.identity.tenant = str(header.value)
            elif header.key == "x-gateway-userid":
                log.identity.user_id = str(header.value)
            elif header.key == "identity":
                log.identity.key_id = str(header.value)
            elif header.key == "content-type":
                callctx["content_type"] = str(header.value).lower()

            # store all but the envoy http-standard headers
            if header.key[0] != ":":
                log.request.headers.append(api.LogMetadata(key=header.key, value=header.value))

        log.record.url = f"{log.record.url}://{log.record.domain}{log.record.path}"

        callctx["log"] = log

        return self.just_continue_headers()

    def process_request_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:

        log = callctx["log"]
        log.request.body.extend(
            encode_body_data(
                body=body.body,
                content_type=callctx["content_type"],
            )
        )
        return self.just_continue_body()

    def process_response_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:

        log = callctx["log"]
        callctx["content_type"] = "text/plain"

        # we loop here because we store all the data
        for header in headers.headers.headers:

            if header.key == ":status":
                log.record.status = int(str(header.value))
            elif header.key == "content-type":  # used in response_body phase
                callctx["content_type"] = str(header.value).lower()

            # store all but the envoy http-standard headers
            if header.key[0] != ":":
                log.response.headers.append(api.LogMetadata(key=header.key, value=header.value))

        return self.just_continue_headers()

    def process_response_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:

        log = callctx["log"]
        log.response.body.extend(
            encode_body_data(
                body=body.body,
                content_type=callctx["content_type"],  # from response_headers phase
            )
        )
        log.record.end_time.GetCurrentTime()
        log.record.duration.FromNanoseconds(
            log.record.end_time.ToNanoseconds() - log.record.start_time.ToNanoseconds()
        )

        # now that we're finished, we can produce the log (using buffering)
        try:
            self._producer.produce(KAFKA_TOPIC, log)
            self._producer.poll(0)  # trigger callbacks, not likely for this message
        except BufferError:
            self._producer.flush()

        return self.just_continue_body()


# non-class helpers


def encode_body_data(
    body: str,
    content_type: str,
) -> List[api.LogMetadata]:
    if content_type == "application/json":
        return encode_json_body_data(body)
    return encode_raw_body_data(body)


def encode_json_body_data(body: str) -> List[api.LogMetadata]:
    data: Dict
    try:
        data = loads(body)
    except JSONDecodeError:
        return encode_raw_body_data(body)
    return [
        api.LogMetadata(key=key, value=value) for key, value in flatten(data, separator=".").items()
    ]


def encode_raw_body_data(body: str) -> List[api.LogMetadata]:
    return [api.LogMetadata(key="raw", value=body)]
