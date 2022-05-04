from concurrent import futures
import logging
from os import environ

from envoy.service.ext_proc.v3.external_processor_pb2_grpc import (
    add_ExternalProcessorServicer_to_server,
    ExternalProcessorServicer,
)
import grpc

from .processors import BaseExternalProcessorService

logger = logging.getLogger(__name__)

GRPC_PORT = environ.get("GRPC_PORT", "50051")
GRPC_WORKERS = int(environ.get("GRPC_WORKERS", "5"))


def serve(service: ExternalProcessorServicer = BaseExternalProcessorService()) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=GRPC_WORKERS))
    logger.info(f"Starting gRPC server {service}")
    add_ExternalProcessorServicer_to_server(service, server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    server.wait_for_termination()
