import asyncio
import logging
from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from pymongo.asynchronous.database import AsyncDatabase

from parser_api.application.port.db.repositories.results.reader import IResultReader
from parser_api.application.port.db.repositories.results.writer import IResultWriter
from parser_api.application.port.parser.parser import IParserProvider
from parser_api.composition.configuration.config import Settings
from parser_api.infrastructure.mongodb.connect import MongoConnector
from parser_api.infrastructure.mongodb.repositories.results.reader import ResultReader
from parser_api.infrastructure.mongodb.repositories.results.writer import ResultWriter
from parser_api.infrastructure.web.digikey.digikey_parser import (
    DigiKeyParserProvider,  # noqa: F401
)
from parser_api.infrastructure.web.lcsc.lcsc_parser import (
    LCSCParserProvider,  # noqa: F401
)
from parser_api.infrastructure.web.mouser.mouser_parser import (
    MouserParserProvider,  # noqa: F401
)
from parser_api.infrastructure.web.octopart.octopart_parser import (
    OctopartParserProvider,  # noqa: F401
)
from parser_api.infrastructure.web.parser_registry import ParserRegistry

logger = logging.getLogger(__name__)


class ParserProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_all_parsers(
        self, configuration: Settings
    ) -> AsyncIterator[list[IParserProvider]]:
        parsers = []
        for cls in IParserProvider.__subclasses__():
            try:
                parsers.append(
                    cls(
                        user_data_dir="./data",  # type: ignore
                        proxy=configuration.proxy,  # type: ignore
                        headless=configuration.HEADLESS,  # type: ignore
                    )
                )
            except Exception as e:
                logger.error("Error creating parser %s: %s", cls.__name__, e)

        await asyncio.gather(*(p.__aenter__() for p in parsers))

        try:
            yield parsers
        finally:
            await asyncio.gather(*(p.__aexit__(None, None, None) for p in parsers))

    @provide
    def get_registry(self, parsers: list[IParserProvider]) -> ParserRegistry:
        return ParserRegistry(parsers)


class DatabaseProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_db(self, configuration: Settings) -> AsyncIterator[AsyncDatabase]:
        async with MongoConnector(configuration.mongo_url) as client:
            db = client[configuration.MONGO_DB_NAME]
            yield db


class DatabaseRepositoryProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_user_reader(self, db: AsyncDatabase) -> IResultReader:
        return ResultReader(db)

    @provide
    def get_user_writer(self, db: AsyncDatabase) -> IResultWriter:
        return ResultWriter(db)


def _infrastructure_provider() -> tuple[Provider, ...]:
    return (
        DatabaseProvider(),
        DatabaseRepositoryProvider(),
        ParserProvider(),
    )
