# recipe-transcribe — local speech-to-text for recipe videos

A YouTube/TikTok video whose recipe lives **only in the spoken narration**
— no captions, thin description — is useless to a recipe app. This fixes
that: it downloads the video's audio, transcribes it **on your own PC**
with whisper.cpp (no cloud, no paid APIs), and writes a plain-text
transcript you paste into Recipe Vault's *"Finish this recipe from its
transcript"* box.

Nothing is uploaded anywhere. Python standard library only.

## How it works

```
video URL / local file
      │  yt-dlp (URLs only)
      ▼
  audio ──► ffmpeg → 16 kHz WAV ──► whisper.cpp (local) ──► transcript-<name>.txt
```

## One-time setup (Windows)

1. Put this `recipe-transcribe` folder **next to** your `podcast-archive`
   folder (it reuses that project's whisper.cpp binary and model). If you
   keep them elsewhere, set the `WHISPER_BIN` and `WHISPER_MODEL`
   environment variables.
2. Install yt-dlp (needed only for URLs, not local files):
   `pip install yt-dlp`

## Use

```
python transcribe-video.py "https://www.youtube.com/watch?v=XXXX"
python transcribe-video.py "C:\Videos\grandma-pasta.mp4"
python transcribe-video.py "<url>" --out "pesto-pasta.txt"
```

It prints where the `transcript-<name>.txt` file landed. Then, in Recipe
Vault: open the recipe → *"Finish this recipe from its transcript"* →
paste the file → extract ingredients & steps.

## Notes

- Transcription runs at roughly 3x the video length on CPU (a 3-minute
  video takes ~8–10 minutes). Real speech recognition, locally, for free.
- Works with YouTube and TikTok links, plus any local audio/video file
  (MP4, MP3, M4A, …).
- If a video **has** captions, you don't need this — it's only for the
  spoken-audio-only case.

## Troubleshooting

- **Download fails (YouTube 403 / "failed to extract")**: run `yt-dlp -U`
  first. If it still fails, get the audio any other way and pass the file
  directly — the transcription half doesn't care where audio came from.
- **"Could not find whisper.cpp or the model"**: the script expects this
  folder next to `podcast-archive`, or set `WHISPER_BIN` / `WHISPER_MODEL`.

## License

MIT — see [LICENSE](LICENSE).
