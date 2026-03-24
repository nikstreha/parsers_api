import logging

from pymongo.asynchronous.database import AsyncDatabase

from parser_api.application.port.db.repositories.results.writer import IResultWriter
from parser_api.infrastructure.mongodb.collections import Collections
from parser_api.infrastructure.mongodb.documents.results import ResultDocument
from parser_api.infrastructure.mongodb.exeptions import WriterError

logger = logging.getLogger(__name__)


class ResultWriter(IResultWriter):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db[Collections.RESULTS]

    async def create_many(self, results: list[ResultDocument]) -> None:
        try:
            docs = [
                ResultDocument.model_validate(result).model_dump() for result in results
            ]

            await self.collection.insert_many(docs)
            logger.debug("Created %s results", len(results))

        except Exception as e:
            logger.error("Error while creating results: %s", e)
            raise WriterError("Error while creating results") from e
