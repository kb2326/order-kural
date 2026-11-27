"""Provider configuration. Keys are read at call time, so the app starts with no keys at all."""
import os


def provider_status() -> dict[str, str]:
    """Report whether each AI provider can be used. All three run on Sarvam today."""
    state = "ready" if os.environ.get("SARVAM_API_KEY", "").strip() else "not_set"
    return {"stt": state, "llm": state, "tts": state}
