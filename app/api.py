"""HTTP API. Money is sent both as paise (for code) and as formatted rupees (for people)."""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path

import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agent import say
from app.audio import AudioError, to_wav16k
from app.obs.trace import span
from app.providers.base import ProviderError, Transcript
from app.providers.costs import stt_paise
from app.providers.sarvam_stt import SarvamSTT
from app.agent.session import AgentSession
from app.agent.text_loop import TextBrain
from app.domain.changes import PieceResult
from app.flow import ask
from app.flow.shop import ShopError, ShopService
from app.domain.money import format_inr
from app.domain.order import Order
from app.domain.rules import compute_totals
from app.flow.pieces import PieceService, PieceStateError, Proposal
from app.store.db import Store

SAMPLE_LABEL = "Sample: saved AI results · synthetic voice"
SAMPLE_FILE = Path(__file__).parent / "sample" / "conversation.json"

router = APIRouter(prefix="/api")


MAX_SAMPLE_SESSIONS = 200


def _svc(request: Request) -> PieceService:
    """The live service, or, when the page sends X-Sample-Session, that browser tab's own in-memory sample.
    Samples never touch the live database, and one visitor's restart cannot wipe another's."""
    session = request.headers.get("X-Sample-Session", "").strip()[:64]
    if not session:
        return request.app.state.pieces
    sessions: OrderedDict[str, PieceService] = request.app.state.sample_sessions
    svc = sessions.get(session)
    if svc is None:
        svc = PieceService(Store(":memory:"), request.app.state.pieces.catalog)
        sessions[session] = svc
        while len(sessions) > MAX_SAMPLE_SESSIONS:
            sessions.popitem(last=False)
    sessions.move_to_end(session)
    return svc


def _totals_json(totals) -> dict:
    return {"subtotal_paise": totals.subtotal_paise, "subtotal": format_inr(totals.subtotal_paise),
            "gst_paise": totals.gst_paise, "gst": format_inr(totals.gst_paise),
            "total_paise": totals.total_paise, "total": format_inr(totals.total_paise)}


def order_json(order: Order, svc: PieceService) -> dict:
    totals = compute_totals(order, svc.catalog)
    lines = []
    for l in order.lines:
        item = svc.catalog.get(l.item_code)
        amount = totals.line_totals[l.item_code]
        lines.append({"item_code": l.item_code, "name": item.name if item else l.item_code, "sizes": l.sizes,
                      "quantity": l.quantity, "rate_paise": l.rate_paise, "rate": format_inr(l.rate_paise),
                      "line_total_paise": amount, "line_total": format_inr(amount), "flags": l.flags,
                      "source_piece_id": l.source_piece_id})
    return {"id": order.id, "customer_name": order.customer_name, "city": order.city, "state": order.state,
            "transport": order.transport, "payment": order.payment, "lines": lines, "totals": _totals_json(totals)}


def proposal_json(p: Proposal, svc: PieceService) -> dict:
    return {"piece_id": p.piece_id, "order_id": p.order_id, "is_new_order": p.is_new_order,
            "order": order_json(p.order, svc), "diff": [asdict(d) for d in p.diff],
            "totals": _totals_json(p.totals), "missing": p.missing, "problems": p.problems,
            "readback": p.readback, "ask_customer": p.ask_customer}


MAX_AGENT_SESSIONS = 200
NOTE_PREFIX = "Forwarded voice note from a buyer: "
NO_KEY = "Sarvam API key not set"


def _key() -> str:
    return os.environ.get("SARVAM_API_KEY", "").strip()


def _agent(request: Request) -> AgentSession:
    """One agent conversation per browser tab (header X-Agent-Session), all sharing the live shop database."""
    return _agent_for(request.app, request.headers.get("X-Agent-Session", ""))


def _agent_for(app, sid: str) -> AgentSession:
    sid = sid.strip()[:64] or "default"
    sessions: OrderedDict[str, AgentSession] = app.state.agent_sessions
    agent = sessions.get(sid)
    if agent is None:
        live = app.state.pieces
        agent = AgentSession(live, ShopService(live.store, live.catalog))
        sessions[sid] = agent
        while len(sessions) > MAX_AGENT_SESSIONS:
            sessions.popitem(last=False)
    sessions.move_to_end(sid)
    return agent


def _brain(request: Request, agent: AgentSession) -> TextBrain:
    brains: dict = request.app.state.text_brains
    brain = brains.get(id(agent))
    if brain is None or brain.session is not agent:
        brain = TextBrain(agent, _key(), client=request.app.state.llm_client)
        brains[id(agent)] = brain
    brain.api_key = _key()
    return brain


def _limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not request.app.state.text_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")


class TextIn(BaseModel):
    text: str


@router.post("/agent/text")
def agent_text(body: TextIn, request: Request) -> dict:
    if not _key():
        raise HTTPException(status_code=503, detail=NO_KEY)
    _limit(request)
    agent = _agent(request)
    return asdict(_brain(request, agent).turn(body.text.strip()[:2000]))


AUDIO_DIR = Path("data/runtime/audio")


def _stt(request: Request):
    return request.app.state.stt or SarvamSTT(_key())


def _transcribe(request: Request, audio: UploadFile) -> Transcript:
    """Save the upload, convert it, and transcribe it (cut at pauses). 422 for unusable audio."""
    suffix = Path(audio.filename or "note.ogg").suffix.lower()[:8] or ".ogg"
    stem = uuid.uuid4().hex
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    src, wav = AUDIO_DIR / f"{stem}{suffix}", AUDIO_DIR / f"{stem}-16k.wav"  # never the same file as the upload
    src.write_bytes(audio.file.read(25 * 1024 * 1024))
    try:
        to_wav16k(src, wav)
        store = request.app.state.pieces.store
        with span(store, None, "stt", "sarvam") as s:
            transcript = _stt(request).transcribe(wav)
            s["cost_paise"] = stt_paise(transcript.seconds_audio)
        return transcript
    except AudioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/agent/transcribe")
def agent_transcribe(request: Request, audio: UploadFile = File(...)) -> dict:
    """Only the words of an uploaded note: the page then sends them over the open voice socket."""
    if not _key():
        raise HTTPException(status_code=503, detail=NO_KEY)
    _limit(request)
    t = _transcribe(request, audio)
    return {"transcript": t.text, "language": t.language}


@router.post("/agent/upload")
def agent_upload(request: Request, audio: UploadFile = File(...)) -> dict:
    """A buyer's forwarded voice note: transcribe it, then give it to the agent like a typed message."""
    if not _key():
        raise HTTPException(status_code=503, detail=NO_KEY)
    _limit(request)
    t = _transcribe(request, audio)
    agent = _agent(request)
    result = asdict(_brain(request, agent).turn(NOTE_PREFIX + t.text))
    return {**result, "transcript": t.text, "language": t.language}


def _tap(request: Request, words: str, action: str) -> dict:
    agent = _agent(request)
    agent.heard(words)
    result = agent.confirm_pending() if action == "confirm" else agent.discard_pending()
    return {"spoken": [result.say], "ui": result.ui, "wrote": result.wrote}


@router.post("/agent/confirm")
def agent_confirm(request: Request) -> dict:
    """The owner tapped Sari: the tap is his approval, same as saying it."""
    return _tap(request, "sari", "confirm")


@router.post("/agent/discard")
def agent_discard(request: Request) -> dict:
    return _tap(request, "cancel", "discard")


@router.websocket("/voice")
async def voice(ws: WebSocket, session: str = "", lang: str = "ta-IN") -> None:
    """Live talk. The browser can't set headers on a WebSocket, so the tab's agent session id comes as ?session=,
    and the reply language as ?lang= (live STT labels code-mixed speech en-IN, so it can't choose the language)."""
    if _key():
        # Pipecat takes seconds to import; doing it in a thread keeps the server answering meanwhile.
        await asyncio.to_thread(importlib.import_module, "app.voice.bot")
    await ws.accept()
    if not _key():
        await ws.close(code=4003, reason=NO_KEY)
        return
    ip = ws.client.host if ws.client else "unknown"
    if not ws.app.state.voice_limiter.allow(ip):
        await ws.close(code=4029, reason="Too many voice sessions. Please try again later.")
        return
    from app.voice.bot import run  # Pipecat loads only when someone talks, so a keyless start never needs it
    agent = _agent_for(ws.app, session)
    agent.language = say.lang(lang)
    await run(ws, agent, _key())


@router.get("/agent/state")
def agent_state(request: Request) -> dict:
    return {"ui": _agent(request).slip()}


def _shop(request: Request) -> ShopService:
    """The live shop, or this tab's sample shop when the page sends X-Sample-Session."""
    svc = _svc(request)
    return ShopService(svc.store, svc.catalog)


@router.get("/bills")
def list_bills(request: Request) -> list[dict]:
    return [{**b, "total": format_inr(b["total_paise"]), "voided": bool(b["voided"])}
            for b in _svc(request).store.recent_bills()]


@router.get("/bills/{number}")
def get_bill(number: int, request: Request) -> dict:
    view = _shop(request).bill_view(number)
    if view is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return view


@router.get("/customers")
def list_customers(request: Request) -> list[dict]:
    shop = _shop(request)
    out = []
    for c in shop.store.all_customers():
        bal = shop.balance(c["id"])
        out.append({**c, "balance_paise": bal, "balance": format_inr(bal)})
    return out


@router.get("/customers/{customer_id}/khata")
def customer_khata(customer_id: int, request: Request) -> dict:
    shop = _shop(request)
    entries = shop.store.ledger_for(customer_id)
    bal = shop.balance(customer_id)
    return {"entries": [{**e, "amount": format_inr(e["amount_paise"])} for e in entries], "balance_paise": bal,
            "balance": format_inr(bal)}


@router.post("/customers/{customer_id}/undo")
def customer_undo(customer_id: int, request: Request) -> dict:
    """Tap-only undo of the latest bill or payment, as a reversal entry (never a delete)."""
    try:
        return {"message": _shop(request).undo_last(customer_id)}
    except ShopError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/to-ship")
def to_ship(request: Request) -> dict:
    svc = _svc(request)
    return ask.to_ship(svc.store, svc.catalog).facts


def _sample_agent(request: Request, fresh: bool = False) -> AgentSession:
    """This tab's sample conversation: the real AgentSession over the tab's own in-memory shop."""
    svc = _svc(request)
    agents: dict = request.app.state.sample_agents
    agent = agents.get(id(svc))
    if fresh or agent is None or agent.pieces is not svc:
        agent = AgentSession(svc, ShopService(svc.store, svc.catalog), source="sample")
        agent.sample_index = 0
        agents[id(svc)] = agent
    return agent


@router.post("/sample/reset")
def sample_reset(request: Request) -> dict:
    _svc(request).store.reset()
    _sample_agent(request, fresh=True)
    return {"ok": True}


@router.post("/sample/next")
def sample_next(request: Request) -> dict:
    """Replay the next saved step: the owner's words, then the tool calls the AI made for them, through the real
    agent. Code builds every spoken sentence, exactly as in live use."""
    agent = _sample_agent(request)
    steps = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))["steps"]
    i = agent.sample_index
    if i >= len(steps):
        raise HTTPException(status_code=409, detail="Sample finished")
    step = steps[i]
    agent.sample_index = i + 1
    agent.heard(step["user_text"], step["language"])
    spoken, bill_number = [], None
    for call in step["tool_calls"]:
        result = agent.call(call["name"], call["args"])
        if result.say:
            spoken.append(result.say)
        bill_number = result.facts.get("number", bill_number) if call["name"] == "confirm_pending" else bill_number
    if not step["tool_calls"]:
        spoken.append(step["assistant_text"])
    n = i + 1
    return {"label": SAMPLE_LABEL, "index": n, "total": len(steps), "user_text": step["user_text"],
            "language": step["language"], "spoken": spoken, "slip": agent.slip(), "bill_number": bill_number,
            "user_audio_url": _sample_audio_url(f"step{n}-user.wav"),
            "bot_audio_url": _sample_audio_url(f"step{n}-bot.wav")}


SAMPLE_AUDIO = Path(__file__).parent / "sample" / "audio"


def _sample_audio_url(name: str) -> str | None:
    return f"/api/sample/audio/{name}" if (SAMPLE_AUDIO / name).exists() else None


@router.get("/sample/audio/{name}")
def sample_audio(name: str) -> FileResponse:
    if not re.fullmatch(r"step\d{1,2}-(user|bot)\.wav", name) or not (SAMPLE_AUDIO / name).exists():
        raise HTTPException(status_code=404, detail="No such sample audio")
    return FileResponse(SAMPLE_AUDIO / name, media_type="audio/wav")


@router.get("/orders")
def list_orders(request: Request) -> list[dict]:
    svc = _svc(request)
    out = []
    for o in svc.store.open_orders():
        t = compute_totals(o, svc.catalog)
        out.append({"id": o.id, "customer_name": o.customer_name, "city": o.city, "state": o.state,
                    "line_count": len(o.lines), "total_paise": t.total_paise, "total": format_inr(t.total_paise)})
    return out


@router.get("/orders/{order_id}")
def get_order(order_id: int, request: Request) -> dict:
    svc = _svc(request)
    order = svc.store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_json(order, svc)
