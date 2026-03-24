from datetime import datetime

from pydantic import BaseModel, Field

from parser_api.application.dto.enums.sites import Sites


class Price(BaseModel):
    qty: int
    price: float = 0


class ResultDocument(BaseModel):
    id_: int | None = Field(alias="_id", default=None)
    part_number: str
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
    date_: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
