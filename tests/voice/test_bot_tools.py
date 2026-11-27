import asyncio

import pytest
from pipecat.frames.frames import OutputTransportMessageUrgentFrame, TTSSpeakFrame

from app.agent.session import AgentSession
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.flow.shop import ShopService
from app.store.db import Store
from app.voice.bot import make_handler

CAT = Catalog.load("data/items.json")


class FakeLLM:
    def __init__(self):
        self.pushed = []

    async def push_frame(self, frame, direction=None):
        self.pushed.append(frame)


class FakeParams:
    def __init__(self, arguments):
        self.arguments = arguments
        self.llm = FakeLLM()
        self.results = []

    async def result_callback(self, result, *, properties=None):
        self.results.append((result, properties))


@pytest.fixture
def session():
    store = Store(":memory:")
    s = AgentSession(PieceService(store, CAT), ShopService(store, CAT))
    s.heard("Kerala Fancy palazzo", "ta-IN")
    return s


def test_write_tool_handler_speaks_say_without_llm(session):
    params = FakeParams({"customer": "Kerala Fancy", "items": [
        {"name_as_spoken": "plain palazzo", "item_code": "PPL", "sizes": {"S": 6, "M": 6}}]})
    asyncio.run(make_handler(session, "add_to_order")(params))
    spoken = [f for f in params.llm.pushed if isinstance(f, TTSSpeakFrame)]
    assert len(spoken) == 1 and "₹780" in spoken[0].text
    events = [f.message for f in params.llm.pushed if isinstance(f, OutputTransportMessageUrgentFrame)]
    assert {"slip", "bot"} <= {e["type"] for e in events}
    [(result, props)] = params.results
    assert props.run_llm is False and result["said_to_owner"] == spoken[0].text


def test_read_tool_handler_lets_llm_answer(session):
    params = FakeParams({"customer": "Kerala Fancy"})
    asyncio.run(make_handler(session, "get_open_order")(params))
    assert not [f for f in params.llm.pushed if isinstance(f, TTSSpeakFrame)]
    [(result, props)] = params.results
    assert props is None and result["facts"]["open_order"] is None


def test_bad_arguments_do_not_crash(session):
    params = FakeParams({"nonsense": 1})
    asyncio.run(make_handler(session, "add_to_order")(params))
    [(result, _)] = params.results
    assert "error" in result["facts"]
