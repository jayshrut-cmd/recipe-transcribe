#!/usr/bin/env python3
"""
recipe-transcribe: turn a cooking video's SPOKEN audio into a plain-text
transcript you can paste into Recipe Vault ("Finish this recipe from its
transcript").

Covers the one case Recipe Vault can't do on its own: a YouTube/TikTok video
whose recipe lives only in the narration (no captions, thin description).

Pipeline:  video URL --yt-dlp--> mp3 --ffmpeg--> 16kHz wav --whisper.cpp--> txt
Everything runs locally on your machine. Stdlib only.

Usage:
    python transcribe-video.py "https://www.youtube.com/watch?v=XXXX"
    python transcribe-video.py "C:\\Videos\\pasta.mp4"      (local audio/video file)
    python transcribe-video.py "<url>" --out "pesto-pasta.txt"

Requirements:
  - ffmpeg on PATH            (you already have this from the podcast-archive setup)
  - yt-dlp on PATH            (only for URLs; `pip install yt-dlp` or grab the exe)
  - whisper.cpp + ggml-base.en model from your podcast-archive install
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Where to look for whisper.cpp. First hit wins. Override with env vars.
WHISPER_CANDIDATES = [
    os.environ.get("WHISPER_BIN", ""),
    os.path.join(SCRIPT_DIR, "..", "podcast-archive", "tools", "whisper.cpp-win", "whisper-cli.exe"),
    os.path.join(SCRIPT_DIR, "..", "podcast-archive", "tools", "whisper-bin-ubuntu-x64", "whisper-cli"),
]
MODEL_CANDIDATES = [
    os.environ.get("WHISPER_MODEL", ""),
    os.path.join(SCRIPT_DIR, "..", "podcast-archive", "models", "ggml-base.en.bin"),
]

TIMESTAMP_LINE = re.compile(r"^\s*\[.*?\]\s*")


def first_existing(paths):
    for p in paths:
        if p and os.path.isfile(os.path.abspath(p)):
            return os.path.abspath(p)
    return None


def run(cmd, **kw):
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"command failed: {' '.join(cmd[:3])}...\n{tail}")
    return proc


def safe_name(text):
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return (text or "video")[:60]


def download_audio(url, tmpdir):
    ytdlp = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if not ytdlp:
        raise RuntimeError(
            "yt-dlp not found. Install it with `pip install yt-dlp`\n"
            "or download yt-dlp.exe from https://github.com/yt-dlp/yt-dlp/releases"
        )
    out_tmpl = os.path.join(tmpdir, "audio.%(ext)s")
    print("Step 1/3: downloading audio…")
    run([ytdlp, "-x", "--audio-format", "mp3", "--no-playlist",
         "-o", out_tmpl, "--print", "after_move:filepath",
         "--print", "title", url])
    mp3 = os.path.join(tmpdir, "audio.mp3")
    if not os.path.isfile(mp3):
        found = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
        if not found:
            raise RuntimeError("yt-dlp finished but no mp3 appeared.")
        mp3 = os.path.join(tmpdir, found[0])
    return mp3


def to_wav(src, tmpdir):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH.")
    wav = os.path.join(tmpdir, "audio16k.wav")
    print("Step 2/3: converting to 16kHz wav…")
    run([ffmpeg, "-y", "-v", "error", "-i", src, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav])
    return wav


def transcribe(wav, tmpdir, whisper_bin, model):
    out_base = os.path.join(tmpdir, "whisper")
    print("Step 3/3: transcribing locally (takes a while on CPU)…")
    run([whisper_bin, "-m", model, "-f", wav, "-otxt", "-of", out_base,
         "-t", str(os.cpu_count() or 4), "-np"])
    txt = out_base + ".txt"
    if not os.path.isfile(txt):
        raise RuntimeError("whisper.cpp finished but produced no transcript file.")
    lines = []
    with open(txt, encoding="utf-8") as fh:
        for line in fh:
            lines.append(TIMESTAMP_LINE.sub("", line).strip())
    return " ".join(t for t in lines if t)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    source = argv[1]
    out_path = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out_path = argv[i + 1]

    whisper_bin = first_existing(WHISPER_CANDIDATES)
    model = first_existing(MODEL_CANDIDATES)
    if not whisper_bin or not model:
        raise RuntimeError(
            "Could not find whisper.cpp or the model.\n"
            "Looked for the binary at:\n  " + "\n  ".join(WHISPER_CANDIDATES) + "\n"
            "and the model at:\n  " + "\n  ".join(MODEL_CANDIDATES) + "\n"
            "Fix: set WHISPER_BIN and WHISPER_MODEL env vars, or keep this folder\n"
            "next to your podcast-archive folder."
        )

    tmpdir = tempfile.mkdtemp(prefix="recipe-transcribe-")
    try:
        if re.match(r"^https?://", source):
            src, title = download_audio(source, tmpdir), "video"
            # grab the video title for a friendly filename
            ytdlp = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
            try:
                t = subprocess.run([ytdlp, "--no-playlist", "--print", "title", source],
                                   capture_output=True, text=True, timeout=60)
                if t.returncode == 0 and t.stdout.strip():
                    title = t.stdout.strip()
            except Exception:
                pass
            name = safe_name(title)
        else:
            if not os.path.isfile(source):
                raise RuntimeError(f"file not found: {source}")
            src = source
            name = safe_name(os.path.splitext(os.path.basename(source))[0])

        wav = to_wav(src, tmpdir)
        transcript = transcribe(wav, tmpdir, whisper_bin, model)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not transcript:
        print("No speech detected in the audio. Nothing written.")
        return 1

    if not out_path:
        out_path = os.path.join(os.getcwd(), f"transcript-{name}.txt")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(transcript + "\n")

    words = len(transcript.split())
    print(f"\nDone. {words} words written to:\n  {out_path}\n")
    print("Next: open the recipe in Recipe Vault → 'Finish this recipe from its")
    print("transcript' → paste the whole file → Extract ingredients & steps.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except RuntimeError as e:
        print(f"\nError: {e}\n", file=sys.stderr)
        sys.exit(2)
