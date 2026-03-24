from fastapi import APIRouter

from parser_api.presentation.http.parsing.controller import router as parsing_router

router = APIRouter()
router.include_router(parsing_router)
