import inspect

import pytest

from app.agent import say
from app.agent.session import TOOL_NAMES, AgentSession
from app.agent.tools import TOOL_SPECS
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.flow.shop import ShopService
from app.store.db import Store

CAT = Catalog.load("data/items.json")
PALAZZO = [{"name_as_spoken": "plain palazzo", "item_code": "PPL", "sizes": {"S": 6, "M": 6, "L": 6, "XL": 6}}]
CROP = [{"name_as_spoken": "crop top", "item_code": "CRT", "sizes": {"M": 10, "L": 10}}]


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def agent(store):
    a = AgentSession(PieceService(store, CAT), ShopService(store, CAT))
    a.heard("Kerala Fancy-ku 24 plain palazzo", "ta-IN")
    return a


def sari(agent):
    agent.heard("சரி", "ta-IN")
    return agent.confirm_pending()


def test_add_to_order_stages_and_says_total(agent, store):
    r = agent.add_to_order("Kerala Fancy", PALAZZO)
    assert r.wrote and agent.pending.kind == "order"
    assert "₹1,560" in r.say and "சரி" in r.say
    assert store.open_orders() == []


def test_say_matches_render_for_staged(agent):
    r = agent.add_to_order("Kerala Fancy", PALAZZO)
    assert r.say == say.render("staged", r.facts, "ta-IN")


def test_second_add_same_customer_merges_into_one_pending(agent, store):
    first = agent.add_to_order("Kerala Fancy", PALAZZO)
    r = agent.add_to_order("Kerala Fancy", CROP)
    assert agent.pending.piece_id != first.facts["piece_id"]
    assert store.get_piece(first.facts["piece_id"])["state"] == "discarded"
    assert r.facts["total_paise"] == 24 * 6500 + 20 * 7500
    sari(agent)
    [order] = store.open_orders()
    assert [l.item_code for l in order.lines] == ["PPL", "CRT"]


def test_other_customer_while_pending_is_refused(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    r = agent.add_to_order("Sri Murugan", CROP)
    assert r.say == say.render("other_pending", {"customer": "Kerala Fancy"}, "ta-IN")
    assert agent.pending.customer == "Kerala Fancy"


def test_confirm_requires_yes_words(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    agent.heard("also add ten shorts", "en-IN")
    r = agent.confirm_pending()
    assert r.say == say.render("need_yes", {"customer": "Kerala Fancy"}, "en-IN")
    assert store.open_orders() == [] and agent.pending is not None


def test_confirm_with_sari_saves(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    r = sari(agent)
    assert r.wrote and agent.pending is None and r.ui["pending"] is None
    assert r.say == say.render("saved", {"customer": "Kerala Fancy", "total_paise": 156000}, "ta-IN")
    [order] = store.open_orders()
    assert order.customer_name == "Kerala Fancy" and order.lines[0].sizes == {"S": 6, "M": 6, "L": 6, "XL": 6}


def test_confirm_with_nothing_pending(agent):
    agent.heard("sari", "ta-IN")
    assert agent.confirm_pending().say == say.render("nothing_pending", {}, "ta-IN")


def test_discard_drops_pending(agent, store):
    r = agent.add_to_order("Kerala Fancy", PALAZZO)
    agent.discard_pending()
    assert agent.pending is None and store.get_piece(r.facts["piece_id"])["state"] == "discarded"


def test_customer_not_said_asks_not_pending(agent):
    r = agent.add_to_order("", PALAZZO)
    assert agent.pending is None and r.say == say.render("ask_customer", {"near": None}, "ta-IN")


def test_near_miss_customer_asks(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    sari(agent)
    r = agent.add_to_order("Kerala Fancies", CROP)
    assert agent.pending is None and "Kerala Fancy" in r.say


def test_bad_item_only_reports_problem_and_keeps_nothing(agent):
    r = agent.add_to_order("Kerala Fancy", [{"name_as_spoken": "silk saree", "quantity_total": 10}])
    assert agent.pending is None and "silk saree" in r.say


def test_bill_then_sari_issues_gst_invoice_and_debit(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO, state="Kerala")
    sari(agent)
    agent.heard("bill it", "ta-IN")
    r = agent.bill_order("Kerala Fancy")
    assert agent.pending.kind == "bill" and "₹1,638" in r.say and "GST" in r.say
    r = sari(agent)
    assert r.facts["number"] == 1 and r.facts["invoice_no"].endswith("/0001")
    assert store.get_bill(1)["total_paise"] == 163800
    cid = store.find_customers("Kerala Fancy")[0]["id"]
    assert agent.shop.balance(cid) == 163800


def test_bill_without_place_of_supply_asks_for_state(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    sari(agent)
    r = agent.bill_order("Kerala Fancy")
    assert agent.pending is None and "state or GSTIN" in r.say


def test_gstin_sets_place_of_supply(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO, gstin="32aakfl4333r1zx")
    sari(agent)
    assert store.open_orders()[0].gstin == "32AAKFL4333R1ZX" and store.open_orders()[0].state_code == "32"


def test_bad_gstin_is_a_problem(agent):
    r = agent.add_to_order("Kerala Fancy", PALAZZO, gstin="12345")
    assert "GSTIN not valid" in r.say


def test_bill_with_no_open_order(agent):
    r = agent.bill_order("Nobody Tex")
    assert agent.pending is None and r.say == say.render("no_open_order", {"customer": "Nobody Tex"}, "ta-IN")


def test_payment_then_sari_updates_balance(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO, state="Kerala")
    sari(agent)
    agent.bill_order("Kerala Fancy")
    sari(agent)
    agent.record_payment("Kerala Fancy", 500, "upi")
    r = sari(agent)
    assert r.facts["balance_paise"] == 163800 - 50000
    assert "₹1,138" in r.say


def test_payment_unknown_customer_asks(agent):
    r = agent.record_payment("Ghost Stores", 500, "upi")
    assert agent.pending is None and r.say == say.render("ask_customer", {"near": None}, "ta-IN")


def test_mark_shipped_then_sari(agent, store):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    sari(agent)
    agent.mark_shipped("Kerala Fancy", "KPN")
    sari(agent)
    assert store.orders_in_states(["shipped"])[0].transport == "KPN"


def test_ask_to_ship_speaks_code_answer_and_writes_nothing(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    sari(agent)
    r = agent.ask_shop("to_ship")
    assert not r.wrote and r.say == say.render("to_ship", {"orders": [{"customer": "Kerala Fancy"}]}, "ta-IN")


def test_ask_unknown_question_cannot_answer(agent):
    assert agent.ask_shop("weather").say == say.render("cannot_answer", {}, "ta-IN")


def test_read_tools_return_facts_and_no_say(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO)
    sari(agent)
    r = agent.get_open_order("Kerala Fancy")
    assert r.say == "" and r.facts["lines"][0]["item"] == "Plain palazzo"
    assert agent.find_customer("Kerala Fancy").facts["matches"][0]["name"] == "Kerala Fancy"


def test_tool_specs_cover_all_methods():
    names = {s["function"]["name"] for s in TOOL_SPECS}
    assert names == set(TOOL_NAMES)
    for name in TOOL_NAMES:
        assert callable(getattr(AgentSession, name))
        params = set(inspect.signature(getattr(AgentSession, name)).parameters) - {"self"}
        spec = next(s for s in TOOL_SPECS if s["function"]["name"] == name)
        assert set(spec["function"]["parameters"]["properties"]) == params


def test_add_to_order_accepts_loose_item_shapes(agent):
    """27 Nov live check: the LLM sent items as strings; the tool crashed and the LLM then spoke unguided."""
    r = agent.add_to_order("Kerala Fancy", ["plain palazzo"])
    assert agent.pending is None and "plain palazzo" in r.say  # no quantity -> a spoken problem, not a crash
    r = agent.add_to_order("Kerala Fancy", '[{"name_as_spoken": "plain palazzo", "item_code": "PPL", '
                                           '"sizes": {"S": 6}}]')
    assert agent.pending is not None and "₹390" in r.say


def test_call_never_raises_on_garbage(agent):
    r = agent.call("add_to_order", {"customer": "Kerala Fancy", "items": 42})
    assert "error" in r.facts or r.say


def test_add_to_order_reassembles_streamed_json_fragments(agent):
    """27 Nov live voice check: Pipecat delivered items as JSON fragments split at commas, plus stray brackets."""
    fragments = ['[{"name_as_spoken": "plain palazzo"', '"item_code": "PPL"', '"sizes": {"S": 6', '"M": 6',
                 '"L": 6', '"XL": 6}}]}]']
    r = agent.add_to_order("Kerala Fancy", fragments)
    assert agent.pending is not None and "₹1,560" in r.say


def test_new_order_with_no_items_is_not_staged(agent):
    """27 Nov eval: a new order with only 'transport KPN' (item quantity missing) was savable at Rs 0."""
    r = agent.add_to_order("Kerala Fancy", [{"name_as_spoken": "print palazzo", "item_code": "PRP"}], transport="KPN")
    assert agent.pending is None and "No quantity for: print palazzo" in r.say


def test_age_band_not_said_is_refused(agent):
    """27 Nov eval: the LLM put '1-10 yrs' on 'shorts set 20', copying a prompt example."""
    agent.heard("Lakshmi Tex-ku shorts set 20", "ta-IN")
    r = agent.add_to_order("Lakshmi Tex", [{"name_as_spoken": "shorts set", "item_code": "SHS",
                                           "sizes": {"1-10 yrs": 20}}])
    assert agent.pending is None and "Size not said: 1-10 yrs" in r.say


def test_age_band_said_in_an_earlier_turn_is_accepted(agent):
    agent.heard("Forwarded voice note from a buyer: girls pant 1 se 10 saal 50 piece", "hi-IN")
    agent.heard("Sri Murugan Tex, Erode", "ta-IN")
    r = agent.add_to_order("Sri Murugan Tex", [{"name_as_spoken": "girls pant", "item_code": "GPT",
                                               "sizes": {"1-10 yrs": 50}}], city="Erode")
    assert agent.pending is not None and "₹2,750" in r.say


def test_invented_sizes_drop_only_those_lines(agent):
    agent.heard("Lakshmi Tex-ku crop top S pathu M pathu, shorts set 20", "ta-IN")
    r = agent.add_to_order("Lakshmi Tex", [
        {"name_as_spoken": "crop top", "item_code": "CRT", "sizes": {"S": 10, "M": 10}},
        {"name_as_spoken": "shorts set", "item_code": "SHS", "sizes": {"1-10 yrs": 20}}])
    assert agent.pending is not None and [l["item"] for l in agent.pending.view["lines"]] == ["Crop top"]
    assert "Size not said: 1-10 yrs" in r.say
