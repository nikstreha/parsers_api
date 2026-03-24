from abc import ABC, abstractmethod

from parser_api.infrastructure.mongodb.documents.results import ResultDocument


class IResultWriter(ABC):
    @abstractmethod
    async def create_many(self, results: list[ResultDocument]) -> None: ...
