"""Central config: API key, base URLs, model ids, supported languages."""
import os

from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")

# Sarvam exposes an OpenAI-compatible chat endpoint; the SDK covers speech + translate.
SARVAM_BASE_URL = "https://api.sarvam.ai"
SARVAM_OPENAI_BASE_URL = f"{SARVAM_BASE_URL}/v1"

# Models (see docs.sarvam.ai). sarvam-30b = lower latency, good for a live voice loop.
CHAT_MODEL = os.environ.get("SARVAM_CHAT_MODEL", "sarvam-30b")
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
# bulbul:v3 speakers (from the API's own error listing). Override via env if you like.
# Female Hindi-friendly options: priya, kavya, shreya, neha, ritu, pooja, ishita.
TTS_SPEAKER = os.environ.get("SARVAM_TTS_SPEAKER", "priya")

# Languages we expose in the UI. Kannada included deliberately (Bengaluru/Karnataka).
LANGUAGES = {
    "Hindi": "hi-IN",
    "Kannada": "kn-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Marathi": "mr-IN",
    "Bengali": "bn-IN",
    "English": "en-IN",
}
DEFAULT_LANG = "hi-IN"


def require_key() -> str:
    if not SARVAM_API_KEY:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://dashboard.sarvam.ai"
        )
    return SARVAM_API_KEY
