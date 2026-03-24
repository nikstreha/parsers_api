from abc import ABC, abstractmethod

from parser_api.infrastructure.mongodb.documents.results import ResultDocument


class IResultReader(ABC):
    @abstractmethod
    async def get_by_id(self, result_id: int) -> ResultDocument | None: ...

    @abstractmethod
    async def get_by_part_number(
        self, part_number: str
    ) -> list[ResultDocument] | None: ...
