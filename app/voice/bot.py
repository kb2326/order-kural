"""The live voice agent: browser mic -> Sarvam realtime STT -> sarvam-105b with our tools -> Bulbul TTS -> browser.

Grounding rule (27 Nov spike): when a tool returns a code-built `say`, that sentence is spoken via TTSSpeakFrame and
the LLM is told not to run again (run_llm=False), so it cannot describe a change that did not happen."""
from __future__ import annotations

import time

from fastapi import WebSocket
from pipecat.frames.frames import (Frame, InputTransportMessageFrame, LLMFullResponseEndFrame, LLMMessagesAppendFrame,
                                   LLMTextFrame,
                                   OutputTransportMessageUrgentFrame, TranscriptionFrame, TTSSpeakFrame)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.llm_service import FunctionCallResultProperties
from pipecat.services.sarvam.llm import SarvamLLMService
from pipecat.services.sarvam.stt import SarvamRealtimeSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.turns.user_start import ExternalUserTurnStartStrategy
from pipecat.turns.user_stop import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from app.agent import say, words
from app.agent.prompt import system_prompt
from app.agent.session import TOOL_NAMES, AgentSession
from app.agent.tools import TOOL_SPECS
from app.voice.wire import RawPCMSerializer

SESSION_SECONDS = 600


def _event(message: dict) -> OutputTransportMessageUrgentFrame:
    return OutputTransportMessageUrgentFrame(message=message)


def make_handler(session: AgentSession, name: str, clock: dict | None = None):
    """A Pipecat function handler that runs one AgentSession tool."""

    async def handler(params) -> None:
        if clock is not None:
            clock["tool_turn"] = True
        result = session.call(name, dict(params.arguments or {}))
        await params.llm.push_frame(_event({"type": "slip", **result.ui}))
        payload = {"facts": result.facts, "said_to_owner": result.say}
        if result.say:
            await params.llm.push_frame(_event({"type": "bot", "text": result.say}))
            await params.llm.push_frame(TTSSpeakFrame(result.say))
            await params.result_callback(payload, properties=FunctionCallResultProperties(run_llm=False))
        else:
            await params.result_callback(payload)

    return handler


class Ears(FrameProcessor):
    """Between STT and the LLM: tells the session what the owner said, switches the voice to his language, runs the
    Sari / Cancel taps, and sends his words to the page."""

    def __init__(self, session: AgentSession, tts: SarvamTTSService, clock: dict):
        super().__init__()
        self.session, self.tts, self.clock = session, tts, clock

    async def _heard(self, text: str) -> None:
        # The reply language is the one the page chose: live codemix STT labels Tamil-in-English-letters "en-IN".
        self.session.heard(text, None)
        self.clock.update(t_user=time.monotonic(), tool_turn=False, said="", warned=False)
        await self.push_frame(_event({"type": "user", "text": text, "lang": self.session.language}))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            await self._heard(frame.text)
        elif isinstance(frame, LLMMessagesAppendFrame) and frame.messages:
            await self._heard(str(frame.messages[-1].get("content", "")))
        elif isinstance(frame, InputTransportMessageFrame) and isinstance(frame.message, dict) \
                and frame.message.get("type") == "tap":
            confirm = frame.message["action"] == "confirm"
            self.session.heard("sari" if confirm else "cancel")
            result = self.session.confirm_pending() if confirm else self.session.discard_pending()
            await self.push_frame(_event({"type": "slip", **result.ui}))
            await self.push_frame(_event({"type": "bot", "text": result.say}))
            await self.push_frame(TTSSpeakFrame(result.say))
            return
        await self.push_frame(frame, direction)


class Mouth(FrameProcessor):
    """After the LLM: sends the LLM's own words to the page and measures time from his last word to the reply."""

    def __init__(self, clock: dict, session: AgentSession):
        super().__init__()
        self.clock, self.session = clock, session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame):
            self.clock["said"] = self.clock.get("said", "") + frame.text
        if isinstance(frame, LLMFullResponseEndFrame) and not self.clock.get("warned") \
                and words.unbacked_claim(self.clock.get("said", ""), self.clock.get("tool_turn", False)):
            # The AI claimed an action no tool performed (27 Nov live check): correct it out loud, in code.
            self.clock["warned"] = True
            fix = say.render("not_done", {}, self.session.language)
            await self.push_frame(frame, direction)
            await self.push_frame(_event({"type": "bot", "text": fix}))
            await self.push_frame(TTSSpeakFrame(fix))
            return
        if isinstance(frame, (LLMTextFrame, TTSSpeakFrame)):
            if self.clock.get("t_user"):
                gap = round(time.monotonic() - self.clock.pop("t_user"), 2)
                await self.push_frame(_event({"type": "latency", "s": gap}))
            if isinstance(frame, LLMTextFrame):
                await self.push_frame(_event({"type": "bot", "text": frame.text, "partial": True}))
        await self.push_frame(frame, direction)


async def run(ws: WebSocket, session: AgentSession, api_key: str) -> None:
    transport = FastAPIWebsocketTransport(websocket=ws, params=FastAPIWebsocketParams(
        audio_in_enabled=True, audio_out_enabled=True, audio_in_sample_rate=16000, audio_out_sample_rate=16000,
        serializer=RawPCMSerializer(), session_timeout=SESSION_SECONDS))
    stt = SarvamRealtimeSTTService(api_key=api_key, endpointing="vad", sample_rate=16000,
                                   settings=SarvamRealtimeSTTService.Settings(model="saaras:v4", mode="codemix"))
    llm = SarvamLLMService(api_key=api_key, settings=SarvamLLMService.Settings(
        model="sarvam-105b", reasoning_effort="none", temperature=0.2,
        system_instruction=system_prompt(session.catalog, session.store.open_orders())))
    clock: dict = {}  # shared per session: last user time, whether a tool ran this turn, the AI's own words
    tts = SarvamTTSService(api_key=api_key, sample_rate=16000, settings=SarvamTTSService.Settings(
        model="bulbul:v3", voice="priya", language=Language(session.language)))
    for name in TOOL_NAMES:
        llm.register_function(name, make_handler(session, name, clock))

    context = LLMContext(tools=_tools_schema())
    user_agg, bot_agg = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(
        user_turn_strategies=UserTurnStrategies(start=[ExternalUserTurnStartStrategy()],
                                                stop=[ExternalUserTurnStopStrategy(timeout=0.3)])))
    pipeline = Pipeline([transport.input(), stt, Ears(session, tts, clock), user_agg, llm, Mouth(clock, session), tts,
                         transport.output(), bot_agg])
    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True))

    @transport.event_handler("on_client_disconnected")
    async def _gone(_transport, _client):
        await worker.cancel()

    await session_greeting(transport, session)
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()


def _tools_schema():
    """Our OpenAI-style tool JSON as Pipecat's provider-neutral schema."""
    from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
    from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
    return ToolsSchema(standard_tools=[
        FunctionSchema(name=s["function"]["name"], description=s["function"]["description"],
                       properties=s["function"]["parameters"]["properties"],
                       required=s["function"]["parameters"]["required"]) for s in TOOL_SPECS])


async def session_greeting(transport, session: AgentSession) -> None:
    """Shows the current slip when the page connects (a pending piece survives a dropped connection)."""
    @transport.event_handler("on_client_connected")
    async def _hello(t, _client):
        await t.output().push_frame(_event({"type": "slip", **session.slip()}))
        await t.output().push_frame(_event({"type": "ready", "language": session.language,
                                            "languages": list(say.LANGUAGES)}))
