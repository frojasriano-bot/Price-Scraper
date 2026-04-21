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
from .sixt_is import SixtIsScraper
from .enterprise_is import EnterpriseIsScraper

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
    SixtIsScraper,
    EnterpriseIsScraper,
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
    "SixtIsScraper",
    "EnterpriseIsScraper",
    "ALL_SCRAPERS",
]
