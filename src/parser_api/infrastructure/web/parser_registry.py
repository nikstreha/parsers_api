import logging

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.port.parser.parser import IParserProvider
from parser_api.infrastructure.web.digikey.digikey_parser import DigiKeyParserProvider
from parser_api.infrastructure.web.lcsc.lcsc_parser import LCSCParserProvider
from parser_api.infrastructure.web.mouser.mouser_parser import MouserParserProvider
from parser_api.infrastructure.web.octopart.octopart_parser import OctopartParserProvider

logger = logging.getLogger(__name__)

PARSER_CLASSES: list[type[IParserProvider]] = [
    DigiKeyParserProvider,
    LCSCParserProvider,
    MouserParserProvider,
    OctopartParserProvider,
]


class ParserRegistry:
    def __init__(self, parsers: list[IParserProvider]):
        self._parsers = {p.source: p for p in parsers}
        logger.info("Initialized with parsers: %s", list(self._parsers.keys()))

    def get_by_source(self, source: Sites) -> IParserProvider:
        parser = self._parsers.get(source)
        if not parser:
            raise ValueError(f"Parser for source {source} not found!")
        return parser
