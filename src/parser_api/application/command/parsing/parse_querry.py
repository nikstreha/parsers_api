import asyncio

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.process import PostProcessingDTO
from parser_api.application.dto.parsing.request import RequestDTO
from parser_api.application.dto.parsing.responce import ResponceDTO
from parser_api.application.port.db.repositories.results.writer import IResultWriter
from parser_api.infrastructure.mongodb.documents.results import Price, ResultDocument
from parser_api.infrastructure.web.parser_registry import ParserRegistry


class ParseQuerryInteractor:
    def __init__(
        self,
        result_writer: IResultWriter,
        registry: ParserRegistry,
    ) -> None:
        self._result_writer = result_writer
        self._registry = registry

    async def __call__(self, querry: RequestDTO) -> ResponceDTO:
        if querry.site == Sites.ALL:
            parsers = [
                self._registry.get_by_source(site)
                for site in Sites
                if site != Sites.ALL
            ]
        else:
            parsers = [self._registry.get_by_source(querry.site)]

        results = await asyncio.gather(
            *[parser.parse(querry.part_number) for parser in parsers]
        )

        postparsing: list[PostProcessingDTO] = [
            item for sublist in results for item in sublist
        ]

        response = ResponceDTO(part_number=querry.part_number)
        for_db = []

        for pars_one in postparsing:
            db_save = ResultDocument(
                part_number=querry.part_number,
                mpn=pars_one.mpn,
                manufacture=pars_one.manufacture,
                description=pars_one.description,
                package=pars_one.package,
                source=pars_one.source,
                distributor=pars_one.distributor,
                currency=pars_one.currency,
                in_stock=pars_one.in_stock,
                url=pars_one.url,
                condition=pars_one.condition,
                country=pars_one.country,
                prices=[
                    Price(qty=price.qty, price=price.price) for price in pars_one.prices
                ],
                lead_time=pars_one.lead_time,
            )
            response.results.append(pars_one)
            for_db.append(db_save)

        if for_db:
            await self._result_writer.create_many(for_db)

        return response
