import pytest

from app.domain.catalog import Catalog
from app.domain.money import format_inr


@pytest.fixture(scope="module")
def cat():
    return Catalog.load("data/items.json")


def test_load_has_13_items(cat):
    assert len(cat.all()) == 13


def test_get_by_code(cat):
    assert cat.get("PRP").rate_paise == 6800
    assert cat.get("NOPE") is None


def test_match_exact_alias_and_case(cat):
    assert cat.match("PRINT PALAZZO").code == "PRP"
    assert cat.match("croptop").code == "CRT"


def test_match_near_spelling(cat):
    assert cat.match("print palazo").code == "PRP"


def test_match_unknown_returns_none(cat):
    assert cat.match("saree") is None


def test_format_inr():
    assert format_inr(832860) == "₹8,328.60"
    assert format_inr(12345678) == "₹1,23,456.78"
    assert format_inr(0) == "₹0.00"


def test_plausible_rejects_other_audience_words(cat):
    gpt = cat.get("GPT")
    assert cat.plausible(gpt, "girls pant")
    assert not cat.plausible(gpt, "teen girls pant")
    assert not cat.plausible(gpt, "women's pant")
    assert not cat.plausible(gpt, "ladies pant")
    assert cat.plausible(cat.get("KPT"), "kids pant")
