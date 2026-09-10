import json

from aiokafka import AIOKafkaProducer


class KafkaEventPublisher:
    """Optional event publisher. Kafka is used for durable event flow, not as a lock."""

    def __init__(self, bootstrap_servers: str, topic: str):
        self.topic = topic
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    async def start(self):
        await self.producer.start()

    async def stop(self):
        await self.producer.stop()

    async def publish(self, event: dict):
        await self.producer.send_and_wait(self.topic, event)
