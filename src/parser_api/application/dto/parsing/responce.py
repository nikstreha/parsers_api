from dataclasses import dataclass, field

from parser_api.application.dto.parsing.process import PostProcessingDTO


@dataclass
class ResponceDTO:
    part_number: str
    results: list[PostProcessingDTO] = field(default_factory=list)
