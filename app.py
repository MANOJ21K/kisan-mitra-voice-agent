"""Kisan Mitra — Gradio voice UI. This is the Hugging Face Spaces entry point.

Speak (or type) a question; the app runs the full Saaras -> Sarvam-30B (+tools) -> Bulbul
pipeline and shows the transcript, the spoken reply, which tools fired, and the
per-stage latency so the engineering is visible, not hidden.
"""
from __future__ import annotations

import tempfile

import gradio as gr

from src import config
from src.pipeline import run_text_turn, run_voice_turn

INTRO = """
# 🌾 Kisan Mitra — किसान मित्र
A multilingual **voice** assistant for Indian farmers, built entirely on Sarvam's stack:
**Saaras v3** (speech-to-text) → **Sarvam-30B** (reasoning + tool-calling) → **Bulbul v3** (text-to-speech).
Ask about mandi prices, weather, crop advice, or government schemes — in your language.
"""


def _audio_to_file(audio_bytes: bytes) -> str | None:
    if not audio_bytes:
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(audio_bytes)
    tmp.flush()
    return tmp.name


def handle_voice(mic_path: str | None, lang_name: str):
    if not mic_path:
        return "—", "Please record a question first.", None, ""
    lang = config.LANGUAGES.get(lang_name, config.DEFAULT_LANG)
    with open(mic_path, "rb") as f:
        turn = run_voice_turn(f.read(), lang=lang)
    return (turn.transcript or "(no speech detected)", turn.reply,
            _audio_to_file(turn.audio),
            f"tools: {', '.join(turn.tools_used) or 'none'}  ·  {turn.timing_summary()}")


def handle_text(text: str, lang_name: str):
    if not text.strip():
        return "Type a question first.", None, ""
    lang = config.LANGUAGES.get(lang_name, config.DEFAULT_LANG)
    turn = run_text_turn(text, lang=lang, speak=True)
    return (turn.reply, _audio_to_file(turn.audio),
            f"tools: {', '.join(turn.tools_used) or 'none'}  ·  {turn.timing_summary()}")


with gr.Blocks(title="Kisan Mitra") as demo:
    gr.Markdown(INTRO)
    lang = gr.Dropdown(choices=list(config.LANGUAGES), value="Hindi", label="Reply language")

    with gr.Tab("🎙️ Speak"):
        mic = gr.Audio(sources=["microphone"], type="filepath", label="Ask your question")
        voice_btn = gr.Button("Ask Kisan Mitra", variant="primary")
        v_transcript = gr.Textbox(label="Heard (Saaras)", interactive=False)
        v_reply = gr.Textbox(label="Reply", interactive=False)
        v_audio = gr.Audio(label="Spoken reply (Bulbul)", autoplay=True)
        v_meta = gr.Markdown()
        voice_btn.click(handle_voice, [mic, lang], [v_transcript, v_reply, v_audio, v_meta])

    with gr.Tab("⌨️ Type"):
        txt = gr.Textbox(label="Ask your question", placeholder="Aaj tamatar ka bhaav kya hai?")
        text_btn = gr.Button("Ask Kisan Mitra", variant="primary")
        t_reply = gr.Textbox(label="Reply", interactive=False)
        t_audio = gr.Audio(label="Spoken reply (Bulbul)", autoplay=True)
        t_meta = gr.Markdown()
        text_btn.click(handle_text, [txt, lang], [t_reply, t_audio, t_meta])
        gr.Examples(
            examples=[
                ["Aaj Kolar mandi mein tamatar ka bhaav kya hai?", "Hindi"],
                ["Any advice for my wheat crop this rabi season?", "English"],
                ["PM Kisan yojana mein kitne paise milte hain?", "Hindi"],
            ],
            inputs=[txt, lang],
        )

    gr.Markdown(
        "Prices, weather, and scheme data in this demo are representative mock data; "
        "the speech, language, and agent stack are live Sarvam APIs. "
        "See the eval harness (`eval/run_eval.py`) for quality + latency numbers."
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
