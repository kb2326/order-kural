import json

import httpx
import pytest

from app.agent.prompt import system_prompt
from app.agent.session import AgentSession
from app.agent.text_loop import FAIL, TextBrain
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.flow.shop import ShopService
from app.store.db import Store

CAT = Catalog.load("data/items.json")


def tool_call(name, args, id="c1"):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 50}}


def text(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 20}}


class Script:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: httpx.Request):
        self.requests.append(json.loads(request.content))
        r = self.responses.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)


def brain(script):
    store = Store(":memory:")
    session = AgentSession(PieceService(store, CAT), ShopService(store, CAT))
    return TextBrain(session, "k", client=httpx.Client(transport=httpx.MockTransport(script))), store


ADD = {"customer": "Kerala Fancy", "items": [{"name_as_spoken": "plain palazzo", "item_code": "PPL",
                                              "sizes": {"S": 6, "M": 6}}]}


def test_prompt_has_rules_items_examples():
    p = system_prompt(CAT, [])
    assert "PPL" in p and "Plain palazzo" in p
    assert "never say you added" in p.lower()
    assert "1-10 yrs" in p and "Girnar Transport" in p
    assert "irupathu naalu" in p


def test_write_tool_say_is_spoken_and_llm_not_called_again():
    script = Script(tool_call("add_to_order", ADD))
    b, store = brain(script)
    r = b.turn("Kerala Fancy-ku plain palazzo S 6 M 6", "ta-IN")
    assert len(script.requests) == 1
    assert len(r.spoken) == 1 and "₹780" in r.spoken[0] and b.session.pending is not None
    assert r.tool_calls[0]["name"] == "add_to_order" and r.error is None
    assert r.cost_paise >= 1 and "chat" in r.timings_ms


def test_read_tool_result_goes_back_to_llm():
    script = Script(tool_call("get_open_order", {"customer": "Kerala Fancy"}), text("No open order yet."))
    b, _ = brain(script)
    r = b.turn("what did Kerala Fancy order?")
    assert len(script.requests) == 2
    tool_msg = script.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert r.spoken == ["No open order yet."]


def test_four_round_cap():
    script = Script(*[tool_call("find_customer", {"name": "X"}, id=f"c{i}") for i in range(4)])
    b, _ = brain(script)
    r = b.turn("who?")
    assert len(script.requests) == 4 and r.error is None


def test_http_error_gives_exact_message():
    b, _ = brain(Script(httpx.Response(500, json={"error": "boom"})))
    r = b.turn("anything")
    assert r.error == FAIL and r.spoken == [FAIL]


def test_bad_tool_arguments_do_not_crash():
    bad = tool_call("add_to_order", {})
    bad["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{not json"
    b, _ = brain(Script(bad, text("Please say it again.")))
    assert b.turn("x").spoken == ["Please say it again."]


def test_request_has_tools_and_model():
    script = Script(text("Vanakkam"))
    b, _ = brain(script)
    b.turn("hello")
    req = script.requests[0]
    assert req["model"] == "sarvam-105b" and req["tool_choice"] == "auto"
    assert {t["function"]["name"] for t in req["tools"]} >= {"add_to_order", "confirm_pending"}
    assert req["messages"][0]["role"] == "system"


def test_history_kept_across_turns():
    script = Script(tool_call("add_to_order", ADD), tool_call("confirm_pending", {}, id="c2"))
    b, store = brain(script)
    b.turn("Kerala Fancy plain palazzo S 6 M 6", "ta-IN")
    r = b.turn("சரி", "ta-IN")
    assert store.open_orders()[0].customer_name == "Kerala Fancy"
    roles = [m["role"] for m in script.requests[1]["messages"]]
    assert roles[:5] == ["system", "user", "assistant", "tool", "assistant"] and roles[-1] == "user"
    assert "₹780" in r.spoken[0]


def test_unbacked_claim_is_corrected_in_code():
    """27 Nov live check: the LLM said 'girls pant ... add panren' without calling a tool."""
    b, _ = brain(Script(text("Kerala Fancy-ku girls pant 50 piece add panren.")))
    r = b.turn("girls pant 50 piece", "ta-IN")
    from app.agent import say
    assert r.spoken[-1] == say.render("not_done", {}, "ta-IN") and len(r.spoken) == 2
