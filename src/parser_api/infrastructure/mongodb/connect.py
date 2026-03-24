import logging
from types import TracebackType

from pymongo import AsyncMongoClient

logger = logging.getLogger(__name__)


class MongoConnector:
    def __init__(self, url: str) -> None:
        self.url = url
        self._client: AsyncMongoClient | None = None

    @property
    def client(self) -> AsyncMongoClient:
        if self._client is None:
            raise RuntimeError("MongoConnector is not connected. Call up() first.")
        return self._client

    def up(self) -> None:
        self._client = AsyncMongoClient(self.url)
        logger.info("MongoConnector connected")

    async def down(self) -> None:
        await self.client.close()
        self._client = None
        logger.info("MongoConnector disconnected")

    async def __aenter__(self) -> AsyncMongoClient:
        self.up()
        return self.client

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.down()
