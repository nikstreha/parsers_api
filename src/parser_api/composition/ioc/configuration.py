from dishka import Provider, Scope, from_context

from parser_api.composition.configuration.config import Settings


class ConfigurationProvider(Provider):
    scope = Scope.APP

    configuration = from_context(provides=Settings)
