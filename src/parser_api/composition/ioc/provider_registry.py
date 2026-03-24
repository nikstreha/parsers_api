from collections.abc import Iterable

from dishka import Provider

from parser_api.composition.ioc.application import _application_provider
from parser_api.composition.ioc.configuration import ConfigurationProvider
from parser_api.composition.ioc.infrastructure import _infrastructure_provider


def get_provider() -> Iterable[Provider]:
    return [
        ConfigurationProvider(),
        *_infrastructure_provider(),
        *_application_provider(),
    ]
