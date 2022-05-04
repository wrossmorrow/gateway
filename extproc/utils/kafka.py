from logging import getLogger
from os import environ
from os.path import exists
from random import randint
from typing import Any, Callable, Dict, Optional

from confluent_kafka import KafkaError, KafkaException, Message, Producer
from ddtrace import tracer
from gateway.kafka.v1.kafka_pb2 import RandomPartitionKey
from google.protobuf.message import Message as ProtoMessage
from protoc_gen_validate.validator import validate, ValidationFailed
from yaml import SafeLoader
from yaml import load as yaml_load

from .utils import dict_env_sub

logger = getLogger(__name__)


DD_SERVICE = environ.get("DD_SERVICE", "extproc")

KAFKA_TOPIC = environ.get("KAFKA_TOPIC", "gateway.logs.v1")

KAFKA_CONFIG_FILE = environ.get("KAFKA_CONFIG_FILE", "/etc/kafka/config.yaml")


# placeholder for rigorous config model for kafka at bond
def kafka_config(config_file: str = KAFKA_CONFIG_FILE) -> Dict:

    if exists(config_file):
        kafka_config = yaml_load(open(config_file, "r"), Loader=SafeLoader)["producer"]
        logger.info(f"Kafka config: {kafka_config}")

        # env sub _after_ print because it might be sensitive
        kafka_config = dict_env_sub(kafka_config)
        return kafka_config

    logger.warning(f"Kafka config file {config_file} does not exist, " "cannot configure kafka")
    return {}


# type aliases for producer callbacks
OnDeliveryCbType = Optional[Callable[[KafkaError, Message], None]]


def random_partition_key() -> RandomPartitionKey:
    return RandomPartitionKey(value=randint(0, 255))


class KafkaConfigException(Exception):
    pass


class InvalidKafkaMessageError(Exception):
    pass


class InvalidKafkaKeyError(InvalidKafkaMessageError):
    pass


class InvalidKafkaValueError(InvalidKafkaMessageError):
    pass


class ProtobufProducer:
    """Wrapper class to implement a Protobuf compliant kafka producer."""

    def __init__(self, **kwargs: Dict[str, Any]):
        logger.debug("Initializing producer.")
        try:
            self._producer = Producer(kwargs)
        except KafkaException as err:
            logger.error(f"Error while initializing kafka: {err}")
            raise KafkaConfigException("Invalid config, failed to initialize producer")

    @tracer.wrap("poll", service=DD_SERVICE, resource="kafka", span_type="kafka")
    def poll(self, timeout: float = -1) -> int:
        return int(self._producer.poll(timeout=timeout))

    @tracer.wrap("produce", service=DD_SERVICE, resource="kafka", span_type="kafka")
    def produce(
        self,
        topic: str,
        value: ProtoMessage,
        key: Optional[ProtoMessage] = None,
        on_delivery: OnDeliveryCbType = None,
    ) -> None:

        # default to uniformly distributed partitions if no key passed
        if key is None:
            key = random_partition_key()

        # ensure topic data integrity with validations on production

        try:
            validate(key)
        except ValidationFailed as err:
            logger.error(f"{err.__class__.__name__} {err}", extra={"error": str(err)})
            raise InvalidKafkaKeyError() from err

        try:
            validate(value)
        except ValidationFailed as err:
            logger.error(f"{err.__class__.__name__} {err}", extra={"error": str(err)})
            raise InvalidKafkaValueError() from err

        logger.debug(
            f"Producing message to {topic}.",
            extra={"topic": topic},
        )

        self._producer.produce(
            topic=topic,
            key=key.SerializeToString(),
            value=value.SerializeToString(),
            callback=on_delivery,
        )
        logger.debug(f"Message produced to topic {topic}", extra={"topic": topic})

    @tracer.wrap("flush", service=DD_SERVICE, resource="kafka", span_type="kafka")
    def flush(self, timeout: float = -1) -> int:
        logger.debug("Flushing producer.")
        return int(self._producer.flush(timeout=timeout))
