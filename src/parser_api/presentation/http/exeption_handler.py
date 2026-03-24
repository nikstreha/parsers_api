import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from playwright._impl._errors import TargetClosedError

from parser_api.infrastructure.exeptions import InfrastructureException
from parser_api.infrastructure.mongodb.exeptions import ReaderError, WriterError
from parser_api.presentation.http.parsing.exeptions import (
    AppError,
    NotFoundError,
    ValidationError,
)
from parser_api.infrastructure.web.exeptions import ParserException

logger = logging.getLogger(__name__)

exc_types = AppError | InfrastructureException


def create_exception_handler(status_code: int, initial_message: str):
    async def exception_handler(_: Request, exc: exc_types):
        logger.error(f"Error: {exc.code} - {exc.message}")  # type: ignore
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "code": exc.code,  # type: ignore
                "message": exc.message,  # type: ignore
                "details": initial_message,
            },
        )

    return exception_handler


def setup_exception_handlers(app: FastAPI):
    app.add_exception_handler(
        NotFoundError,
        create_exception_handler(status.HTTP_404_NOT_FOUND, "Resource not found"),  # type: ignore
    )
    app.add_exception_handler(
        ValidationError,
        create_exception_handler(status.HTTP_400_BAD_REQUEST, "Validation failed"),  # type: ignore
    )
    app.add_exception_handler(
        ReaderError,
        create_exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR, "Reader error"),  # type: ignore
    )
    app.add_exception_handler(
        WriterError,
        create_exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR, "Writer error"),  # type: ignore
    )

    app.add_exception_handler(
        ParserException,
        create_exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR, "ALLERT"),  # type: ignore
    )

    app.add_exception_handler(
        TargetClosedError,
        create_exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR, "ALLERT"),  # type: ignore
    )

    @app.exception_handler(Exception)
    async def global_internal_error(request: Request, exc: Exception):
        logger.exception("Unhandled exception occurred")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )
