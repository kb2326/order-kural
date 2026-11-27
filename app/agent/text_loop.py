"""The text brain: Sarvam chat with tool calling, driving an AgentSession. Used for typed input, uploaded voice notes
and the eval. Rule: when a tool returns a `say`, that code-built sentence is spoken and the LLM is not asked to add
anything, so it cannot describe a change that did not happen."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from app.agent.prompt import system_prompt
from app.agent.session import AgentSession
from app.agent.tools import TOOL_SPECS
from app.obs.trace import span
from app.providers.costs import chat_paise

URL = "https://api.sarvam.ai/v2/chat/completions"
MODEL = "sarvam-105b"
FAIL = "Couldn't understand that. Please say it again, or type it."
MAX_ROUNDS = 4
HISTORY = 30


@dataclass
class TurnResult:
    spoken: list[str]
    tool_calls: list[dict] = field(default_factory=list)
    ui: dict = field(default_factory=dict)
    timings_ms: dict = field(default_factory=dict)
    cost_paise: int = 0
    error: str | None = None


class TextBrain:
    def __init__(self, session: AgentSession, api_key: str, client: httpx.Client | None = None):
        self.session = session
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=45)
        self.messages: list[dict] = []

    def _chat(self, result: TurnResult) -> dict:
        body = {"model": MODEL, "temperature": 0.2, "reasoning_effort": "none", "tool_choice": "auto",
                "tools": TOOL_SPECS,
                "messages": [{"role": "system", "content": system_prompt(self.session.catalog,
                                                                          self.session.store.open_orders())}]
                + self.messages[-HISTORY:]}
        start = time.perf_counter()
        with span(self.session.store, None, "chat", "sarvam") as s:
            r = self.client.post(URL, json=body, headers={"api-subscription-key": self.api_key})
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage") or {}
            s["cost_paise"] = chat_paise(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            s["meta"] = {"usage": usage}
        result.cost_paise += s["cost_paise"]
        result.timings_ms["chat"] = result.timings_ms.get("chat", 0) + int((time.perf_counter() - start) * 1000)
        return data["choices"][0]["message"]

    def turn(self, user_text: str, language: str | None = None) -> TurnResult:
        self.session.heard(user_text, language)
        self.messages.append({"role": "user", "content": user_text})
        result = TurnResult(spoken=[])
        try:
            for _ in range(MAX_ROUNDS):
                msg = self._chat(result)
                calls = msg.get("tool_calls") or []
                if not calls:
                    text = (msg.get("content") or "").strip()
                    self.messages.append({"role": "assistant", "content": text})
                    if text:
                        result.spoken.append(text)
                    break
                self.messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
                spoke = []
                for call in calls:
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = None
                    out = (self.session.call(name, args) if isinstance(args, dict)
                           else self.session._quiet({"error": "Arguments were not valid JSON"}))
                    result.tool_calls.append({"name": name, "args": args, "say": out.say, "wrote": out.wrote})
                    self.messages.append({"role": "tool", "tool_call_id": call["id"],
                                          "content": json.dumps({"facts": out.facts, "said_to_owner": out.say},
                                                                ensure_ascii=False, default=str)})
                    if out.say:
                        spoke.append(out.say)
                if spoke:
                    result.spoken += spoke
                    self.messages.append({"role": "assistant", "content": " ".join(spoke)})
                    break
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            result.error = FAIL
            result.spoken = [FAIL]
        result.ui = self.session.slip()
        return result
