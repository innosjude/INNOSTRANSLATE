import os
import re
import subprocess
import tempfile
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from huggingface_hub import InferenceClient
from langdetect import detect, LangDetectException

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app)

# Allow reasonably large uploads. Your hosting provider may impose its own limit.
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-large-v3")
MYMEMORY_EMAIL = os.getenv("MYMEMORY_EMAIL", "").strip()

LANG_NAMES = {
    "auto": "Auto Detect",
    "en": "English",
    "fr": "French",
    "ja": "Japanese",
    "es": "Spanish",
    "ko": "Korean",
    "zh": "Chinese",
    "de": "German",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "it": "Italian",
    "tr": "Turkish",
}

# MyMemory generally accepts ISO language codes. Map a few common variants.
MM_CODES = {
    "zh": "zh-CN",
    "pt": "pt-PT",
    "en": "en",
    "fr": "fr",
    "ja": "ja",
    "es": "es",
    "ko": "ko",
    "de": "de",
    "ar": "ar",
    "hi": "hi",
    "ru": "ru",
    "it": "it",
    "tr": "tr",
}


def ffmpeg_extract_audio(video_path: Path, audio_path: Path):
    """Extract mono 16 kHz WAV for speech recognition."""
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(audio_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError("FFmpeg could not extract audio from this file.")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def srt_time(seconds):
    seconds = max(0.0, float(seconds))
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def translate_mymemory(text, source, target):
    text = clean_text(text)
    if not text:
        return ""

    if source == target:
        return text

    source = MM_CODES.get(source, source)
    target = MM_CODES.get(target, target)

    params = {
        "q": text[:4500],
        "langpair": f"{source}|{target}",
    }
    if MYMEMORY_EMAIL:
        params["de"] = MYMEMORY_EMAIL

    r = requests.get(
        "https://api.mymemory.translated.net/get",
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if data.get("responseStatus") not in (200, "200", None):
        raise RuntimeError(data.get("responseDetails") or "Translation service rejected the request.")

    translated = data.get("responseData", {}).get("translatedText", "")
    if not translated:
        raise RuntimeError("Translation service returned no translated text.")
    return translated


def translate_chunks(chunks, source, target):
    """Translate each subtitle chunk independently so timings remain aligned."""
    out = []
    for chunk in chunks:
        text = clean_text(chunk["text"])
        if not text:
            continue

        translated = translate_mymemory(text, source, target)
        out.append({
            "start": chunk["start"],
            "end": max(chunk["end"], chunk["start"] + 0.5),
            "source": text,
            "text": clean_text(translated),
        })
    return out


def make_srt(chunks):
    lines = []
    for i, item in enumerate(chunks, start=1):
        lines.append(str(i))
        lines.append(f'{srt_time(item["start"])} --> {srt_time(item["end"])}')
        lines.append(item["text"])
        lines.append("")
    return "\n".join(lines)


def detect_language(text, requested):
    if requested and requested != "auto":
        return requested
    try:
        code = detect(text)
        return code if code in LANG_NAMES else code
    except LangDetectException:
        return "unknown"


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "INNOSTRANSLATE",
        "hf_configured": bool(HF_TOKEN),
        "whisper_model": WHISPER_MODEL,
    })


@app.post("/api/translate")
def translate():
    if not HF_TOKEN:
        return jsonify({
            "error": "The backend is running, but HF_TOKEN has not been configured on the server."
        }), 500

    uploaded = request.files.get("file")
    source = (request.form.get("from") or "auto").lower()
    target = (request.form.get("to") or "en").lower()
    subtitles = (request.form.get("subtitles") or "true").lower() == "true"
    dubbing = (request.form.get("dubbing") or "false").lower() == "true"

    if not uploaded:
        return jsonify({"error": "No video or audio file was uploaded."}), 400
    if target not in LANG_NAMES or target == "auto":
        return jsonify({"error": "Choose a valid target language."}), 400
    if source != "auto" and source not in LANG_NAMES:
        return jsonify({"error": "Choose a valid source language."}), 400
    if source != "auto" and source == target:
        return jsonify({"error": "Source and target languages must be different."}), 400

    if dubbing:
        # Deliberately return a clear message instead of pretending to create a dubbed video.
        return jsonify({
            "error": "AI Voice dubbing is not enabled in this release. Turn off AI Voice and use Add Subtitles."
        }), 400

    with tempfile.TemporaryDirectory(prefix="innostranslate_") as td:
        td = Path(td)
        suffix = Path(uploaded.filename or "").suffix.lower() or ".bin"
        input_path = td / f"input{suffix}"
        audio_path = td / "audio.wav"
        uploaded.save(input_path)

        try:
            ffmpeg_extract_audio(input_path, audio_path)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            client = InferenceClient(
                provider="auto",
                api_key=HF_TOKEN,
            )
            result = client.automatic_speech_recognition(
                audio=str(audio_path),
                model=WHISPER_MODEL,
                extra_body={"return_timestamps": True},
            )
        except Exception as exc:
            return jsonify({
                "error": f"Speech recognition failed: {exc}"
            }), 502

        transcript = clean_text(getattr(result, "text", "") or "")
        raw_chunks = getattr(result, "chunks", None) or []

        chunks = []
        for item in raw_chunks:
            timestamp = getattr(item, "timestamp", None)
            text = clean_text(getattr(item, "text", "") or "")
            if not timestamp or len(timestamp) < 2 or not text:
                continue
            start = timestamp[0]
            end = timestamp[1]
            if start is None:
                continue
            if end is None:
                end = start + 2
            chunks.append({"start": float(start), "end": float(end), "text": text})

        # Some providers may return no timestamp chunks. Keep the app useful by
        # producing one timed subtitle from the full transcript.
        if not chunks and transcript:
            chunks = [{"start": 0.0, "end": 10.0, "text": transcript}]

        if not transcript:
            return jsonify({"error": "No speech was detected in the uploaded media."}), 422

        detected = detect_language(transcript, source)

        try:
            translated_chunks = translate_chunks(chunks, detected, target)
        except Exception as exc:
            return jsonify({
                "error": f"Text translation failed: {exc}"
            }), 502

        translated_full = "\n".join(x["text"] for x in translated_chunks if x["text"])
        srt = make_srt(translated_chunks) if subtitles else ""

        return jsonify({
            "ok": True,
            "detected": LANG_NAMES.get(detected, detected),
            "detected_code": detected,
            "target": LANG_NAMES.get(target, target),
            "translation": translated_full,
            "srt": srt,
            "chunks": translated_chunks,
        })


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File is too large. Try a smaller video or audio file."}), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
