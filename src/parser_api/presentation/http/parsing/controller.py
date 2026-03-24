from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute, inject
from fastapi import APIRouter, status

from parser_api.application.command.parsing.parse_querry import ParseQuerryInteractor
from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.request import RequestDTO
from parser_api.presentation.http.parsing.schema import (
    MetadataSchema,
    Price,
    ResponceSchema,
)

router = APIRouter(
    prefix="/parsing",
    tags=["Parsing"],
    route_class=DishkaRoute,
)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Get parsing result by part number",
    response_model=ResponceSchema,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Part number not found"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid part number or site"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@inject
async def get_parsing_result(
    part_number: str,
    site: Sites,
    interactor: FromDishka[ParseQuerryInteractor],
) -> ResponceSchema:
    response_dto = await interactor(RequestDTO(part_number=part_number, site=site))

    responce = ResponceSchema(
        part_number=response_dto.part_number,
        results=[
            MetadataSchema(
                source=res.source,
                distributor=res.distributor,
                mpn=res.mpn,
                manufacture=res.manufacture,
                description=res.description,
                package=res.package,
                currency=res.currency,
                in_stock=res.in_stock,
                lead_time=res.lead_time,
                url=res.url,
                condition=res.condition,
                country=res.country,
                prices=[
                    Price(qty=price.qty, price=price.price) for price in res.prices
                ],
                date_=res.date_,
            )
            for res in response_dto.results
        ],
    )

    return responce
