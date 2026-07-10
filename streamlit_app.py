"""Kisan Mitra — Streamlit voice chat. App entry point.

A single multi-turn conversation: speak (Saaras transcribes) or type, the reply streams in
token by token from Sarvam-30B (tools resolved inline), and the Bulbul voiceover autoplays
when the text finishes. Per-turn tools + latency are shown under each reply.
"""
from __future__ import annotations

import io

import streamlit as st

from src import config
from src.agent import run_agent_stream
from src.sarvam_client import synthesize, transcribe

st.set_page_config(page_title="Kisan Mitra", page_icon="🌾", layout="centered")

with st.sidebar:
    st.header("🌾 Kisan Mitra")
    st.caption("Multilingual farmer voice assistant, built entirely on Sarvam's stack.")
    lang_name = st.selectbox("Reply language", list(config.LANGUAGES), index=0)
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.caption(
        "**Saaras v3** (STT) → **Sarvam-30B** (reasoning + tools) → **Bulbul v3** (TTS). "
        "Weather (Open-Meteo) and mandi prices (data.gov.in) are live; crop advisory and "
        "schemes are curated reference data."
    )

st.title("Kisan Mitra — किसान मित्र")
st.caption("Ask about mandi prices, weather, crop advice, or government schemes — "
           "speak or type, in your language.")

if "messages" not in st.session_state:
    st.session_state.messages = []          # [{role, content, caption?, audio?}]
if "queued" not in st.session_state:
    st.session_state.queued = None
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

# Example prompts (one-click).
ex_cols = st.columns(3)
EXAMPLES = [
    "Aaj Kolar mandi mein tamatar ka bhaav?",
    "Kya aaj dawa chhidak sakta hoon? Main Kolar mein hoon.",
    "PM Kisan mein kitne paise milte hain?",
]
for col, ex in zip(ex_cols, EXAMPLES, strict=False):
    if col.button(ex, use_container_width=True):
        st.session_state.queued = ex
        st.rerun()

# Replay the conversation so far.
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("audio"):
            st.audio(m["audio"], format="audio/wav", autoplay=False)
        if m.get("caption"):
            st.caption(m["caption"])

# --- input: mic + text ---
audio_val = st.audio_input("🎙️ Speak your question")
typed = st.chat_input("Type your question…")

user_text, asr_ms = None, 0.0
if st.session_state.queued:
    user_text, st.session_state.queued = st.session_state.queued, None
elif typed:
    user_text = typed
elif audio_val is not None:
    data = audio_val.getvalue()
    sig = hash(data)
    if data and sig != st.session_state.last_audio:   # transcribe each recording once
        st.session_state.last_audio = sig
        f = io.BytesIO(data)
        f.name = "speech.wav"
        try:
            user_text, asr_ms = transcribe(f)
        except Exception as e:
            st.error(f"Could not transcribe audio: {e}")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    # Prior turns (text only) become the agent's conversation memory.
    hist = [{"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1] if m["content"]]

    with st.chat_message("assistant"):
        status = st.status("🤔 thinking…", expanded=False)
        placeholder = st.empty()
        meta: dict = {}
        reply = ""
        for kind, text in run_agent_stream(user_text, hist, meta):
            if kind == "status":
                status.update(label=text)
            else:
                reply += text
                placeholder.markdown(reply + " ▌")
        placeholder.markdown(reply)
        status.update(label="done", state="complete")

        lang = config.LANGUAGES.get(lang_name, config.DEFAULT_LANG)
        audio_bytes, tts_ms = b"", 0.0
        try:
            audio_bytes, tts_ms = synthesize(reply, lang=lang)
        except Exception:
            audio_bytes = b""
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav", autoplay=True)

        tools = ", ".join(dict.fromkeys(meta.get("tools_used", []))) or "none"
        caption = (f"🔧 {tools} · ASR {asr_ms:.0f} ms · "
                   f"LLM {meta.get('llm_ms', 0):.0f} ms · TTS {tts_ms:.0f} ms")
        st.caption(caption)

    st.session_state.messages.append({
        "role": "assistant", "content": reply,
        "audio": audio_bytes or None, "caption": caption,
    })
