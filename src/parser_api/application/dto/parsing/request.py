from dataclasses import dataclass

from parser_api.application.dto.enums.sites import Sites


@dataclass(frozen=True)
class RequestDTO:
    part_number: str
    site: Sites
