"""GST registration facts: GSTIN format, state codes, and the place of supply for a buyer."""
from __future__ import annotations

import re

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

STATES = {"jammu and kashmir": "01", "himachal pradesh": "02", "punjab": "03", "delhi": "07", "rajasthan": "08",
          "uttar pradesh": "09", "bihar": "10", "west bengal": "19", "odisha": "21", "madhya pradesh": "23",
          "gujarat": "24", "maharashtra": "27", "karnataka": "29", "goa": "30", "lakshadweep": "31", "kerala": "32",
          "tamil nadu": "33", "puducherry": "34", "telangana": "36", "andhra pradesh": "37"}
STATE_NAMES = {code: name.title() for name, code in STATES.items()}
# Buyer towns seen in the shop's trade (Tamil Nadu, Kerala, Karnataka). Unknown towns: the owner must say the state.
CITY_STATE = {**{c: "33" for c in ("tirupur", "tiruppur", "erode", "coimbatore", "chennai", "madurai", "salem",
                                   "trichy", "tiruchirappalli", "karur", "namakkal", "dindigul", "pollachi")},
              **{c: "32" for c in ("palakkad", "manjeri", "thodupuzha", "kochi", "cochin", "ernakulam", "thrissur",
                                   "kozhikode", "calicut", "malappuram", "kottayam", "kollam", "kannur",
                                   "thiruvananthapuram", "trivandrum", "alappuzha", "perinthalmanna")},
              **{c: "29" for c in ("bengaluru", "bangalore", "mysuru", "mysore", "mangaluru", "mangalore", "hubli")}}


def valid_gstin(gstin: str) -> bool:
    return bool(GSTIN_RE.match(gstin.strip().upper()))


def state_code_for(gstin: str | None, city: str | None) -> str | None:
    """Place of supply: the GSTIN's first two digits, else the buyer's town, else unknown (None)."""
    if gstin and valid_gstin(gstin):
        return gstin.strip()[:2]
    return CITY_STATE.get((city or "").strip().casefold())


def state_code_from_name(name: str) -> str | None:
    key = name.strip().casefold()
    return key if key in STATE_NAMES else STATES.get(key)
