from contextlib import asynccontextmanager

from dishka import AsyncContainer, Provider, make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI

from parser_api.composition.configuration.config import Settings
from parser_api.composition.ioc.provider_registry import get_provider
from parser_api.presentation.http.api_router import router as api_router
from parser_api.presentation.http.exeption_handler import setup_exception_handlers


def create_ioc_container(
    configuration: Settings,
    *di_providers: Provider,
) -> AsyncContainer:
    return make_async_container(
        *get_provider(),
        *di_providers,
        FastapiProvider(),
        context={Settings: configuration},
    )


def create_api_app(container: AsyncContainer) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await container.close()

    app = FastAPI(debug=True, lifespan=lifespan)
    setup_exception_handlers(app)

    app.include_router(api_router)

    setup_dishka(container, app)

    return app


def build_api_app() -> FastAPI:
    configuration = Settings()  # type: ignore
    container = create_ioc_container(configuration)
    return create_api_app(container)
