from datetime import date

from pydantic import BaseModel, Field

from parser_api.application.dto.enums.sites import Sites


class Price(BaseModel):
    qty: int
    price: float = 0


class MetadataSchema(BaseModel):
    mpn: str
    manufacture: str
    source: Sites
    description: str
    distributor: str
    package: str
    currency: str
    in_stock: int
    lead_time: str
    url: str
    condition: str
    country: str
    prices: list[Price]
    date_: date = Field(default_factory=date.today)


class ResponceSchema(BaseModel):
    part_number: str
    results: list[MetadataSchema] = Field(default_factory=list)
