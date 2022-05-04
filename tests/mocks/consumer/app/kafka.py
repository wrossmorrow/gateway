from dataclasses import dataclass
from logging import getLogger
from os import environ
from os.path import exists
from os.path import expandvars as _expandvars
from typing import Any, Dict, List, Optional, Union

from confluent_kafka import Consumer, KafkaException, Message, TopicPartition
from ddtrace import tracer
from flatten_json import flatten, unflatten_list
from google.protobuf.message import Message as ProtoMessage
from google.protobuf.reflection import GeneratedProtocolMessageType
import yaml

logger = getLogger(__name__)


DD_SERVICE = environ.get("DD_SERVICE", "extproc")

KAFKA_TOPIC = environ.get("KAFKA_TOPIC", "gateway.logs.v1")

KAFKA_CONFIG_FILE = environ.get("KAFKA_CONFIG_FILE", "/etc/kafka/config.yaml")


class KafkaConfigError(Exception):
    pass


@dataclass
class TopicConfig:
    topic: str
    key_type: GeneratedProtocolMessageType
    value_type: GeneratedProtocolMessageType


# placeholder for rigorous config model for kafka at bond
def kafka_config(config_file: str = KAFKA_CONFIG_FILE) -> Dict:

    if exists(config_file):
        logger.info(f"Reading kafka config from: {config_file}")
        kafka_config = yaml.load(open(config_file, "r"), Loader=yaml.SafeLoader)["consumer"]

        print(kafka_config)

        # env sub after print because it might be sensitive
        kafka_config = dict_env_sub(kafka_config)
        return kafka_config

    else:
        msg = f"Kafka config file {config_file} does not exist, cannot configure kafka"
        logger.error(msg)
        raise KafkaConfigError(msg)

    return {}


def dict_env_sub(data: Dict, separator: str = ".") -> Dict:
    return unflatten_list({k: expandvars(v) for k, v in flatten(data).items()})


def expandvars(val: Union[str, bytes, int, bool]) -> Union[str, bytes, int, bool]:
    if isinstance(val, str):
        return _expandvars(val)
    elif isinstance(val, bytes):
        return _expandvars(val)
    return val


class ProtobufConsumer:
    """A simple protobuf kafka consumer"""

    def __init__(self, config: TopicConfig, **kwargs: Dict[str, Any]):

        self._stop = False

        if not config:
            raise KafkaConfigError("Invalid config, cannot be empty.")
        if not isinstance(config, TopicConfig):
            raise KafkaConfigError("Invalid config, must be TopicConfig.")
        if not config.topic:
            raise KafkaConfigError("Invalid topic, cannot be empty.")

        self.config = config

        try:
            self._consumer = Consumer(kwargs)
        except KafkaException as err:
            logger.error(f"Error while initializing kafka: {err}")
            raise KafkaConfigError("Invalid config, failed to initialize consumer")

        self._consumer.subscribe([self.config.topic], on_assign=self.assigned)
        logger.debug(f"Consumer subscribed to topic {self.config.topic}.")

    def assigned(self, consumer: Consumer, partitions: List[TopicPartition]) -> None:
        logger.info(f"assigned to {partitions}")

    def consume(self, timeout: float = 1.0) -> None:
        try:
            while not self._stop:
                msg: Message = self._poll(timeout)
                if msg:
                    self._consume(msg)
        except KeyboardInterrupt:
            self._stop = True
        finally:
            logger.info("Consumer closed.")
            self._consumer.close()

    def _poll(self, timeout: float = 1.0) -> Optional[Message]:

        msg: Message = self._consumer.poll(timeout=timeout)

        if msg is None:
            return None

        if msg.error():
            logger.error(
                f"Consumer error: {msg.error()} for topic {msg.topic()}",
                extra={
                    "error": msg.error(),
                    "topic": msg.topic(),
                },
            )
            return None

        return msg

    @tracer.wrap("consume", service=DD_SERVICE, resource="kafka", span_type="kafka")
    def _consume(self, msg: Message) -> bool:
        """while annoying, this gives reasonable tracing semantics"""
        key, value = self.config.key_type(), self.config.value_type()
        key.ParseFromString(msg.key())
        value.ParseFromString(msg.value())
        return self.process(key, value)

    def process(self, key: ProtoMessage, value: ProtoMessage) -> bool:
        raise NotImplementedError("subclass implementation required")
