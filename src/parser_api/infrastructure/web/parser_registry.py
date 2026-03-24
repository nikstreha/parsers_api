import logging

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.port.parser.parser import IParserProvider

logger = logging.getLogger(__name__)


class ParserRegistry:
    def __init__(self, parsers: list[IParserProvider]):
        self._parsers = {p.source: p for p in parsers}
        logger.info("Initialized with parsers: %s", list(self._parsers.keys()))

    def get_by_source(self, source: Sites) -> IParserProvider:
        parser = self._parsers.get(source)
        if not parser:
            raise ValueError(f"Parser for source {source} not found!")
        return parser
