import logging

from pymongo.asynchronous.database import AsyncDatabase

from parser_api.application.port.db.repositories.results.reader import IResultReader
from parser_api.infrastructure.mongodb.collections import Collections
from parser_api.infrastructure.mongodb.documents.results import ResultDocument
from parser_api.infrastructure.mongodb.exeptions import ReaderError

logger = logging.getLogger(__name__)


class ResultReader(IResultReader):
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db[Collections.RESULTS]

    async def get_by_id(self, result_id: int) -> ResultDocument | None:
        try:
            doc = await self.collection.find_one({"_id": result_id})

            if not doc:
                logger.debug("No result found by id %s", result_id)
                return None

            logger.debug("Found result by id %s", result_id)
            return ResultDocument.model_validate(doc)

        except Exception as e:
            logger.error("Error while getting result by id %s: %s", result_id, e)
            raise ReaderError(f"Error while getting result by id {result_id}") from e

    async def get_by_part_number(self, part_number: str) -> list[ResultDocument] | None:
        try:
            cursor = self.collection.find({"part_number": part_number})

            docs = await cursor.to_list()

            if not docs:
                logger.debug("No results found by part number %s", part_number)
                return None

            logger.debug("Found %s results by part number %s", len(docs), part_number)
            return [ResultDocument.model_validate(doc) for doc in docs]

        except Exception as e:
            logger.error(
                "Error while getting results by part number %s: %s", part_number, e
            )
            raise ReaderError(
                f"Error while getting results by part number {part_number}"
            ) from e
