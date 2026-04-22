"""Scrapers package for Blue Rental Intelligence."""

from .blue_rental import BlueCarRentalScraper
from .gocarrental import GoCarRentalScraper
from .lavacarrental import LavaCarRentalScraper
from .hertz_is import HertzIsScraper
from .lotus import LotusCarRentalScraper
from .avis_is import AvisIsScraper
from .holdur import HoldurScraper
from .goiceland_com import GoIcelandScraper
from .mycar_is import MyCarIsScraper

ALL_SCRAPERS = [
    BlueCarRentalScraper,
    GoCarRentalScraper,
    LavaCarRentalScraper,
    HertzIsScraper,
    LotusCarRentalScraper,
    AvisIsScraper,
    HoldurScraper,
    GoIcelandScraper,
    MyCarIsScraper,
]

__all__ = [
    "BlueCarRentalScraper",
    "GoCarRentalScraper",
    "LavaCarRentalScraper",
    "HertzIsScraper",
    "LotusCarRentalScraper",
    "AvisIsScraper",
    "HoldurScraper",
    "GoIcelandScraper",
    "MyCarIsScraper",
    "ALL_SCRAPERS",
]
