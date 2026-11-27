"""What travels on the /api/voice WebSocket between the browser and the bot.

Browser -> bot: binary = microphone PCM16 mono 16 kHz; text JSON {"type":"note","text"} (a forwarded voice note's
transcript) or {"type":"tap","action":"confirm"|"discard"} (the Sari / Cancel buttons).
Bot -> browser: binary = speech PCM16 mono 16 kHz; text JSON events (user, bot, slip, latency, clear)."""
from __future__ import annotations

import json

from pipecat.frames.frames import (AudioRawFrame, Frame, InputAudioRawFrame, InputTransportMessageFrame,
                                   InterruptionFrame, LLMMessagesAppendFrame, OutputTransportMessageFrame,
                                   OutputTransportMessageUrgentFrame)
from pipecat.serializers.base_serializer import FrameSerializer

NOTE_PREFIX = "Forwarded voice note from a buyer: "


class RawPCMSerializer(FrameSerializer):
    def __init__(self):
        super().__init__(FrameSerializer.InputParams(audio_in_sample_rate=16000, audio_out_sample_rate=16000,
                                                     ignore_rtvi_messages=True))

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, InterruptionFrame):
            await self._reset_audio_out()
            return json.dumps({"type": "clear"})
        if isinstance(frame, AudioRawFrame):
            return await self._resample_audio_out(frame) or None
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            if self.should_ignore_frame(frame):
                return None
            return json.dumps(frame.message, ensure_ascii=False)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            return InputAudioRawFrame(audio=await self._resample_audio_in(data), sample_rate=self._sample_rate,
                                      num_channels=1)
        try:
            msg = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(msg, dict):
            return None
        if msg.get("type") == "note" and str(msg.get("text", "")).strip():
            return LLMMessagesAppendFrame(messages=[{"role": "user", "content": NOTE_PREFIX + msg["text"].strip()}],
                                          run_llm=True)
        if msg.get("type") == "tap" and msg.get("action") in ("confirm", "discard"):
            return InputTransportMessageFrame(message={"type": "tap", "action": msg["action"]})
        return None
