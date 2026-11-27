import pytest

from app.agent import say

FACTS = {
    "staged": {"customer": "Kerala Fancy", "changes": ["Plain palazzo: S 6, M 6, L 6, XL 6"], "total_paise": 156000,
               "problems": []},
    "saved": {"customer": "Kerala Fancy", "total_paise": 156000},
    "discarded": {},
    "nothing_pending": {},
    "need_yes": {"customer": "Kerala Fancy"},
    "other_pending": {"customer": "Kerala Fancy"},
    "ask_customer": {"near": None},
    "bill_staged": {"customer": "Kerala Fancy", "total_paise": 2655200},
    "bill_saved": {"number": 12, "total_paise": 2655200},
    "payment_staged": {"customer": "Kerala Fancy", "amount_paise": 1000000, "mode": "upi"},
    "payment_saved": {"customer": "Kerala Fancy", "balance_paise": 1655200},
    "shipped_staged": {"customer": "Kerala Fancy", "transport": "KPN"},
    "shipped_saved": {"customer": "Kerala Fancy"},
    "to_ship": {"orders": [{"customer": "Kerala Fancy"}, {"customer": "Sri Murugan"}]},
    "customer_summary": {"customer": "Kerala Fancy", "open_lines": [{"item": "Crop top", "qty": "M 10"}],
                         "balance_paise": 1655200},
    "item_count": {"item": "Girls pant", "quantity": 50, "days": 7},
    "cannot_answer": {},
    "not_done": {},
    "problems": {"customer": "Kerala Fancy", "problems": ["Unknown item: silk saree"]},
    "no_open_order": {"customer": "Kerala Fancy"},
}


def test_render_staged_tamil_has_total_and_sari():
    text = say.render("staged", FACTS["staged"], "ta-IN")
    assert "Kerala Fancy" in text and "₹1,560" in text and "சரி" in text


def test_render_staged_lists_problems():
    facts = dict(FACTS["staged"], problems=["No quantity for: crop top"])
    assert "No quantity for: crop top" in say.render("staged", facts, "en-IN")


def test_ask_customer_with_near_match_names_it():
    assert "Kerala Fancy" in say.render("ask_customer", {"near": "Kerala Fancy"}, "en-IN")


@pytest.mark.parametrize("language", say.LANGUAGES)
@pytest.mark.parametrize("kind", list(FACTS))
def test_render_every_kind_every_language_nonempty(kind, language):
    assert say.render(kind, FACTS[kind], language).strip()


def test_money_format_indian_grouping():
    assert say.money(2655200) == "₹26,552"
    assert say.money(313110) == "₹3,131.10"
    assert say.money(-100000) == "-₹1,000"


def test_lang_maps_stt_codes():
    assert say.lang("ta-IN") == "ta-IN"
    assert say.lang("en-IN") == "en-IN"
    assert say.lang("ml") == "ml-IN"
    assert say.lang(None) == "ta-IN"
    assert say.lang("te-IN") == "en-IN"
