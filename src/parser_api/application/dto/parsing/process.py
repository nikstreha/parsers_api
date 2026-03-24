from dataclasses import dataclass, field
from datetime import date

from parser_api.application.dto.enums.sites import Sites


@dataclass(frozen=True)
class PriceDTO:
    qty: int
    price: float = 0


@dataclass(frozen=True)
class PostProcessingDTO:
    source: Sites
    mpn: str
    manufacture: str
    description: str
    package: str
    distributor: str
    in_stock: int
    lead_time: str
    currency: str
    prices: list[PriceDTO]
    url: str
    condition: str
    country: str
    date_: date = field(default_factory=date.today)
