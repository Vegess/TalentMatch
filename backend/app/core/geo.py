"""Countries (ISO 3166-1 alpha-2), timezones (IANA) and regions. Display names come from the browser (Intl)."""
from functools import lru_cache
from typing import Optional

COUNTRY_CODES = set("""AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT
BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO
FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE
KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE
SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE
VG VI VN VU WF WS YE YT ZA ZM ZW""".split())

# Default billing currency for a client's country (everything else → USD).
EUR_COUNTRIES = set("AT BE CY DE EE ES FI FR GR HR IE IT LT LU LV MT NL PT SI SK".split())


def default_currency(country: Optional[str]) -> str:
    if not country or country == "IN":  # India-first platform: unknown country → INR
        return "INR"
    if country == "GB":
        return "GBP"
    if country in EUR_COUNTRIES:
        return "EUR"
    return "USD"


@lru_cache(maxsize=1)
def timezones() -> frozenset:
    try:
        from zoneinfo import available_timezones
        return frozenset(available_timezones())
    except Exception:  # pragma: no cover
        return frozenset()


def valid_timezone(tz: str) -> bool:
    zones = timezones()
    if zones:
        return tz in zones
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz)
        return True
    except Exception:
        return False


REGIONS = {"asia": ("Asia/", "Indian/"), "europe": ("Europe/",), "americas": ("America/", "US/", "Canada/"),
           "africa": ("Africa/",), "oceania": ("Australia/", "Pacific/", "NZ")}


def region_of(tz: Optional[str]) -> Optional[str]:
    if not tz:
        return None
    for name, prefixes in REGIONS.items():
        if tz.startswith(prefixes):
            return name
    return None
