"""Kisan Mitra — streaming multi-turn voice chat. App entry point.

A single conversation: speak (Saaras transcribes) or type, the reply streams in token by
token from Sarvam-30B (with tool calls resolved first), and the Bulbul voiceover autoplays
when the text finishes. Per-turn tools + latency are shown as a caption.
"""
from __future__ import annotations

import os
import tempfile

import gradio as gr

from src import config
from src.agent import run_agent_stream
from src.sarvam_client import synthesize, transcribe

INTRO = """
# 🌾 Kisan Mitra — किसान मित्र
A multilingual **voice** assistant for Indian farmers, built entirely on Sarvam's stack:
**Saaras v3** (speech-to-text) → **Sarvam-30B** (reasoning + tool-calling) → **Bulbul v3** (text-to-speech).
Ask about mandi prices, weather, crop advice, or government schemes — speak or type, in your language.
"""

FOOTER = (
    "Weather (Open-Meteo) and mandi prices (data.gov.in Agmarknet) are **live**; crop advisory "
    "and scheme details are **curated reference data**. Speech, reasoning, and voice are live "
    "Sarvam APIs. See `eval/run_eval.py` for quality + latency numbers."
)


def _msg_text(content) -> str:
    """Chat message content may be a plain string or Gradio's multimodal parts list
    ([{'type': 'text', 'text': ...}]); flatten either to a string for the LLM."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict)).strip()
    return str(content or "")


def _audio_to_file(audio_bytes: bytes) -> str | None:
    if not audio_bytes:
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(audio_bytes)
    tmp.flush()
    return tmp.name


def respond(user_text: str, mic_path: str | None, history: list[dict], lang_name: str):
    """Streaming chat turn: resolve input → stream the reply → autoplay the voiceover.

    Yields (chatbot, voice_audio, caption, textbox, mic) on each step so the UI updates
    live as tokens arrive.
    """
    history = history or []
    asr_ms = 0.0

    text = (user_text or "").strip()
    if not text and mic_path:  # voice input: transcribe with Saaras
        try:
            with open(mic_path, "rb") as f:
                text, asr_ms = transcribe(f.read())
        except Exception as e:
            yield history, None, f"Could not read audio: {e}", gr.update(), None
            return
    text = (text or "").strip()
    if not text:
        yield history, None, "Speak or type a question first.", gr.update(), None
        return

    # Prior turns become the agent's conversation memory (text only).
    agent_history = []
    for m in history:
        if m.get("role") in ("user", "assistant"):
            content = _msg_text(m.get("content"))
            if content:
                agent_history.append({"role": m["role"], "content": content})

    history = history + [
        {"role": "user", "content": text},
        {"role": "assistant", "content": ""},
    ]
    yield history, None, "🤔 thinking…", gr.update(value=""), None

    meta: dict = {}
    reply = ""
    for delta in run_agent_stream(text, agent_history, meta):
        reply += delta
        history[-1]["content"] = reply
        yield history, None, "💬 replying…", gr.update(value=""), None

    # Voiceover of the finished reply (Bulbul), autoplayed.
    lang = config.LANGUAGES.get(lang_name, config.DEFAULT_LANG)
    audio_path, tts_ms = None, 0.0
    try:
        audio_bytes, tts_ms = synthesize(reply, lang=lang)
        audio_path = _audio_to_file(audio_bytes)
    except Exception:
        audio_path = None

    tools = ", ".join(dict.fromkeys(meta.get("tools_used", []))) or "none"
    caption = (f"🔧 tools: {tools}  ·  ASR {asr_ms:.0f} ms · "
               f"LLM {meta.get('llm_ms', 0):.0f} ms · TTS {tts_ms:.0f} ms")
    yield history, audio_path, caption, gr.update(value=""), None


with gr.Blocks(title="Kisan Mitra", theme=gr.themes.Soft()) as demo:
    gr.Markdown(INTRO)

    lang = gr.Dropdown(choices=list(config.LANGUAGES), value="Hindi",
                       label="Reply language", scale=1)

    chatbot = gr.Chatbot(height=460, label="Conversation")

    with gr.Row():
        txt = gr.Textbox(scale=6, show_label=False, autofocus=True,
                         placeholder="Type your question — or record with the mic →")
        mic = gr.Audio(sources=["microphone"], type="filepath", scale=2, label="🎙️ Speak")

    with gr.Row():
        send_btn = gr.Button("Send", variant="primary", scale=3)
        clear_btn = gr.Button("Clear chat", scale=1)

    voice_audio = gr.Audio(label="🔊 Voice reply", autoplay=True, interactive=False)
    caption = gr.Markdown()

    gr.Examples(
        examples=[
            "Aaj Kolar mandi mein tamatar ka bhaav kya hai?",
            "Kya main aaj apni fasal par dawa chhidak sakta hoon? Main Kolar mein hoon.",
            "PM Kisan yojana mein kitne paise milte hain?",
        ],
        inputs=txt,
        label="Try one",
    )

    gr.Markdown(FOOTER)

    outputs = [chatbot, voice_audio, caption, txt, mic]
    send_btn.click(respond, [txt, mic, chatbot, lang], outputs)
    txt.submit(respond, [txt, mic, chatbot, lang], outputs)
    clear_btn.click(lambda: ([], None, "", None),
                    outputs=[chatbot, voice_audio, caption, mic])


if __name__ == "__main__":
    # Bind to the platform-provided port (Render/Cloud Run set $PORT); default for local.
    port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", 7860)))
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)
