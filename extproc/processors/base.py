from logging import getLogger
from typing import Dict, Iterator, List, Optional, Union

from envoy.config.core.v3.base_pb2 import (
    HeaderValueOption as EnvoyHeaderValueOption,
)
from envoy.config.core.v3.base_pb2 import HeaderValue as EnvoyHeaderValue
from envoy.service.ext_proc.v3 import external_processor_pb2 as ext_api
from envoy.service.ext_proc.v3.external_processor_pb2_grpc import (
    ExternalProcessorServicer,
)
from grpc import ServicerContext

from ..utils.timing import Timer

logger = getLogger(__name__)


class BaseExternalProcessorService(ExternalProcessorServicer):
    """
    Base ExternalProcessor for envoy. Subclass this and supply
    more specific action methods if desired.
    """

    def Process(
        self,
        request_iterator: Iterator[ext_api.ProcessingRequest],
        context: ServicerContext,
    ) -> Iterator[ext_api.ProcessingResponse]:
        """
        Basic stream handler. This creates a "local" ("call") context
        for each request and walks through the request iterator
        calling (implemented) phase-specific methods for each
        HTTP request phase envoy sends data for. Implement those
        "process_..." methods in subclasses to assert behavior.

        The local/call context ("callctx") is _particularly_ important
        in envoy because the stream will only get data in each phase
        that is immediately relevant to that phase; headers gets headers,
        body gets body. So if a processor needs headers to process
        a body, we have to store that in the header phase.

        Also defines some helpers like get_header (to get a request
        header in a header phase) and add/remove_header for changing
        headers.
        """

        # for each stream, define a new "call" context
        callctx = {"__overhead_ns": 0}
        for request in request_iterator:

            phase_name = request.WhichOneof("request")
            action_name = f"process_{phase_name}"
            action = getattr(self, action_name)
            phase_data = getattr(request, phase_name)

            # look for previous request phase overhead?

            # actually process the request phase
            logger.debug(f"{self.__class__.__name__} started {phase_name}")
            T = Timer()
            with T:
                response = action(phase_data, context, callctx)
            duration = T.duration.ToNanoseconds()
            callctx["__overhead_ns"] += duration
            logger.debug(
                f"{self.__class__.__name__} finished {phase_name} ({duration*1e-9} seconds)"
            )

            # how to store the data in the headers for chaining?
            # actually, probably write events to kafka

            # yield response for the streaming (push/pull) request
            if isinstance(response, ext_api.ImmediateResponse):
                yield ext_api.ProcessingResponse(**{"immediate_response": response})
            else:
                yield ext_api.ProcessingResponse(**{phase_name: response})

    # phase-specific methods below here; override to
    # specialize filter behavior, these will simply move on

    def process_request_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:
        return self.just_continue_headers()

    def process_request_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:
        return self.just_continue_body()

    def process_request_trailers(
        self,
        trailers: ext_api.HttpTrailers,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.TrailersResponse, ext_api.ImmediateResponse]:
        return self.just_continue_trailers()

    def process_response_headers(
        self,
        headers: ext_api.HttpHeaders,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.HeadersResponse, ext_api.ImmediateResponse]:
        return self.just_continue_headers()

    def process_response_body(
        self,
        body: ext_api.HttpBody,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.BodyResponse, ext_api.ImmediateResponse]:
        return self.just_continue_body()

    def process_response_trailers(
        self,
        trailers: ext_api.HttpTrailers,
        grpcctx: ServicerContext,
        callctx: Dict,
    ) -> Union[ext_api.TrailersResponse, ext_api.ImmediateResponse]:
        return self.just_continue_trailers()

    # some boilerplate; not really encapsulating anything but
    # possibly useful methods

    def just_continue_response(self) -> ext_api.CommonResponse:
        """generic "move on" response object (can be modified)"""
        return ext_api.CommonResponse(
            status=ext_api.CommonResponse.ResponseStatus.CONTINUE,
            header_mutation=ext_api.HeaderMutation(
                set_headers=[],
                remove_headers=[],
            ),
        )

    def just_continue_headers(self) -> ext_api.HeadersResponse:
        """generic "move on" headers response object (can be modified)"""
        return ext_api.HeadersResponse(response=self.just_continue_response())

    def just_continue_body(self) -> ext_api.BodyResponse:
        """generic "move on" body response object (can be modified)"""
        return ext_api.BodyResponse(response=self.just_continue_response())

    def just_continue_trailers(self) -> ext_api.TrailersResponse:
        """generic "move on" trailers response object (can be modified)"""
        return ext_api.TrailersResponse(header_mutation=ext_api.HeaderMutation())

    # helpers

    def get_header(self, headers: ext_api.HttpHeaders, name: str, lower_cased: bool = False) -> str:
        """get a header value by name (envoy uses lower cased names)"""
        _name = name if lower_cased else name.lower()
        for header in headers.headers.headers:
            if header.key == _name:
                return header.value
        return None

    def get_headers(
        self,
        headers: ext_api.HttpHeaders,
        names: List[str],  # Union[List[str], Dict[str, str]],
        lower_cased: bool = False,
        mapping: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """get multiple header values by name (envoy uses lower cased names)"""
        results = {}
        _names = names if lower_cased else [name.lower() for name in names]
        ctxkeys = {
            _names[i]: (_names[i] if mapping is None else mapping[i]) for i in range(len(names))
        }
        for header in headers.headers.headers:
            if header.key in _names:
                name = ctxkeys[header.key]
                results[name] = header.value
        return results

    def add_header(
        self, response: ext_api.CommonResponse, key: str, value: str
    ) -> ext_api.CommonResponse:
        """add a header to a CommonResponse"""
        header = EnvoyHeaderValue(key=key, value=value)
        response.header_mutation.set_headers.append(EnvoyHeaderValueOption(header=header))
        return response

    def remove_header(self, response: ext_api.CommonResponse, name: str) -> ext_api.CommonResponse:
        """remove a header from a CommonResponse"""
        response.header_mutation.remove_headers.append(name)
        return response
