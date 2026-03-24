from dishka import Provider, Scope, provide

from parser_api.application.command.parsing.parse_querry import ParseQuerryInteractor
from parser_api.application.port.db.repositories.results.writer import IResultWriter
from parser_api.composition.configuration.config import Settings
from parser_api.infrastructure.web.parser_registry import ParserRegistry


class CommandProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_parse_querry_interactor(
        self, result_writer: IResultWriter, registry: ParserRegistry, config: Settings
    ) -> ParseQuerryInteractor:
        return ParseQuerryInteractor(result_writer, registry, config)


def _application_provider() -> tuple[Provider, ...]:
    return (CommandProvider(),)
