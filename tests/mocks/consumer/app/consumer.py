from logging import getLogger

from gateway.kafka.v1.kafka_pb2 import RandomPartitionKey
from gateway.log.v1.log_pb2 import Log

from .kafka import kafka_config, KAFKA_TOPIC, ProtobufConsumer, TopicConfig

logger = getLogger(__name__)


class APILoggerConsumer(ProtobufConsumer):
    def __init__(self) -> None:
        KAFKA_CONFIG = kafka_config()
        TOPIC_CONFIG = TopicConfig(
            topic=KAFKA_TOPIC,
            key_type=RandomPartitionKey,
            value_type=Log,
        )
        super().__init__(TOPIC_CONFIG, **KAFKA_CONFIG)

    def process(
        self,
        key: RandomPartitionKey,
        value: Log,
    ) -> bool:
        logger.info(f"consumed log message {value.identity.tenant} {value.identity.key_id}")
        return True
