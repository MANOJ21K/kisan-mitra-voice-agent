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
# Stronger model used only by the eval harness as an LLM-as-judge (eval/judge.py).
JUDGE_MODEL = os.environ.get("SARVAM_JUDGE_MODEL", "sarvam-105b")
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
# bulbul:v3 voices: priya, kavya, shreya, neha, ritu, pooja, ishita.
TTS_SPEAKER = os.environ.get("SARVAM_TTS_SPEAKER", "priya")

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

# Open-Meteo is keyless; data.gov.in falls back to a rate-limited public sample key.
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DATA_GOV_IN_API_KEY = os.environ.get(
    "DATA_GOV_IN_API_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
)
AGMARKNET_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
AGMARKNET_URL = f"https://api.data.gov.in/resource/{AGMARKNET_RESOURCE_ID}"
HTTP_TIMEOUT_S = 8.0


def require_key() -> str:
    if not SARVAM_API_KEY:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://dashboard.sarvam.ai"
        )
    return SARVAM_API_KEY
