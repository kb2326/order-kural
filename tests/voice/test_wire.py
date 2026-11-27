import asyncio
import json

from pipecat.frames.frames import (InputAudioRawFrame, InputTransportMessageFrame, InterruptionFrame,
                                   LLMMessagesAppendFrame, OutputAudioRawFrame, OutputTransportMessageUrgentFrame)

from app.voice.wire import RawPCMSerializer


def run(coro):
    return asyncio.run(coro)


class Setup:
    audio_in_sample_rate = 16000


def serializer():
    s = RawPCMSerializer()
    run(s.setup(Setup()))
    return s


def test_serializer_pcm_roundtrip():
    s = serializer()
    pcm = (b"\x01\x00" * 320)
    frame = run(s.deserialize(pcm))
    assert isinstance(frame, InputAudioRawFrame) and frame.sample_rate == 16000 and len(frame.audio) == len(pcm)
    out = run(s.serialize(OutputAudioRawFrame(audio=pcm, sample_rate=16000, num_channels=1)))
    assert isinstance(out, bytes) and len(out) == len(pcm)


def test_serializer_note_message_becomes_user_text():
    frame = run(serializer().deserialize(json.dumps({"type": "note", "text": "girls pant 50"})))
    assert isinstance(frame, LLMMessagesAppendFrame) and frame.run_llm is True
    assert frame.messages == [{"role": "user", "content": "Forwarded voice note from a buyer: girls pant 50"}]


def test_serializer_tap_becomes_transport_message():
    frame = run(serializer().deserialize(json.dumps({"type": "tap", "action": "confirm"})))
    assert isinstance(frame, InputTransportMessageFrame) and frame.message == {"type": "tap", "action": "confirm"}


def test_serializer_events_and_interruptions():
    s = serializer()
    assert json.loads(run(s.serialize(OutputTransportMessageUrgentFrame(message={"type": "slip"})))) == {"type": "slip"}
    assert json.loads(run(s.serialize(InterruptionFrame()))) == {"type": "clear"}


def test_serializer_ignores_bad_json():
    assert run(serializer().deserialize("{not json")) is None
