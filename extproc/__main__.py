import logging

from . import processors
from .service import serve

logger = logging.getLogger(__name__)


def is_service(svc: str):
    if hasattr(processors, svc):
        return svc
    raise AttributeError(f"{svc} is not defned in processors")


def run() -> None:
    """main run function. this pattern will be easier to test."""

    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command", help="sub-command help")

    runner: argparse.ArgumentParser = subparsers.add_parser(
        "run", help="run the grpc server (default, no arg)"
    )
    runner.add_argument(
        "-s",
        "--service",
        dest="service",
        required=False,
        type=is_service,
        default="BaseExternalProcessorService",
        help="Processor to use",
    )

    args: argparse.Namespace = parser.parse_args()

    if args.command == "run":
        try:
            service = getattr(processors, args.service)()
            serve(service=service)
        except KeyboardInterrupt:
            exit(0)
        finally:
            logger.info("Closing gRPC server")

    else:
        raise ValueError(f"Unknown command {args.command}")


if __name__ == "__main__":  # pragma: no cover
    run()
