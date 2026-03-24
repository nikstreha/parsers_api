from abc import ABC, abstractmethod

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.process import PostProcessingDTO


class IParserProvider(ABC):
    @property
    @abstractmethod
    def source(self) -> Sites: ...

    @abstractmethod
    async def parse(
        self, part_number: str, min_delay: int = 2, max_delay: int = 5
    ) -> list[PostProcessingDTO]: ...
