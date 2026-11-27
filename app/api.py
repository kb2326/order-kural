"""HTTP API. Money is sent both as paise (for code) and as formatted rupees (for people)."""
from __future__ import annotations

import asyncio
import importlib
import json
import os
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket
from pydantic import BaseModel

from app.agent import say
from app.agent.session import AgentSession
from app.agent.text_loop import TextBrain
from app.domain.changes import PieceResult
from app.flow.shop import ShopService
from app.domain.money import format_inr
from app.domain.order import Order
from app.domain.rules import compute_totals
from app.flow.pieces import PieceService, PieceStateError, Proposal
from app.store.db import Store

SAMPLE_LABEL = "Sample: saved AI results"
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


@router.post("/sample/reset")
def sample_reset(request: Request) -> dict:
    _svc(request).store.reset()
    return {"ok": True}


@router.post("/sample/next")
def sample_next(request: Request) -> dict:
    svc = _svc(request)
    pieces = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))["pieces"]
    done = svc.store.count_pieces("sample")
    if done >= len(pieces):
        raise HTTPException(status_code=409, detail="Sample finished")
    piece = pieces[done]
    proposal = svc.propose(piece["transcript"], PieceResult.model_validate(piece["ai_result"]), source="sample")
    return {"label": SAMPLE_LABEL, "index": done + 1, "total": len(pieces), "transcript": piece["transcript"],
            "proposal": proposal_json(proposal, svc)}


@router.post("/pieces/{piece_id}/confirm")
def confirm_piece(piece_id: int, request: Request) -> dict:
    svc = _svc(request)
    try:
        return order_json(svc.confirm(piece_id), svc)
    except PieceStateError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/pieces/{piece_id}/discard")
def discard_piece(piece_id: int, request: Request) -> dict:
    try:
        _svc(request).discard(piece_id)
    except PieceStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


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
