---
name: youtube-transcript
description: Get the transcript and source metadata (title, channel, subscribers, upload date, views, duration, description) of any YouTube video in seconds, so a video can be read, quoted and cited like a web page. Uses YouTube's own captions when they exist and falls back to local speech-to-text when they don't. Use whenever a task involves what a YouTube video says, such as researching with videos as sources, summarizing or fact-checking a video, pulling quotes or timestamps, or comparing several videos. Also use when the user pastes a youtube.com or youtu.be link and asks about it. Use this rather than fetching a YouTube page directly, because a fetched page returns little more than the title.
---

# YouTube transcript

Fetches a video's transcript plus the metadata you need to judge it as a source. It runs in its own Python environment at `~/.claude/youtube-transcript-env`, created once on first use (see **First-time setup**).

## Run it
Use exactly this command shape (the web-researcher agent's shell only allows this). Keep both paths in double quotes:

```bash
"<ENV_PYTHON>" "${CLAUDE_PLUGIN_ROOT}/skills/youtube-transcript/scripts/yt_transcript.py" VIDEO_ID [VIDEO_ID ...] [options]
```

`<ENV_PYTHON>` is the tool's own Python:
- Windows: `~/.claude/youtube-transcript-env/Scripts/python.exe`
- macOS / Linux: `~/.claude/youtube-transcript-env/bin/python`

- Pass **11-character video IDs** (the `v=` value, or the part after `youtu.be/` or `/shorts/`). A plain `https://youtu.be/ID` or `https://www.youtube.com/watch?v=ID` URL also works, but strip anything after the ID such as `&t=` or `&list=`.
- Several IDs in one call are processed one after another.

| Option | Use |
|---|---|
| `--meta-only` | Metadata only (about 3 s). Use it to vet several candidate videos before reading any transcript. |
| `--lang es,en` | Preferred caption languages, in order. Default `en`. If none match, you get whatever language exists, and the output says which. |
| `--no-whisper` | Never fall back to local speech-to-text (for speed). |
| `--whisper-model base` | Smaller, faster speech-to-text model (`tiny`, `base`, `small` default, `medium`). |
| `--max-whisper-minutes N` | Skip speech-to-text for videos longer than N minutes (default 45). |
| `--refresh` | Ignore the cached copy. |

## What you get
1. **Metadata:** title, URL, channel (subscribers, verified badge), channel URL, upload date, duration, views, and the start of the description.
2. **Transcript:** paragraphs of about 30 seconds, each starting with a `[m:ss]` timestamp. The `Source:` line says how it was made:
   - **manual captions:** written by the uploader. Most reliable.
   - **auto-generated captions:** YouTube's speech recognition. Names, numbers and technical terms are often wrong.
   - **local speech-to-text:** produced on this machine. It has the same caveat as auto-generated captions.

Speed:
- Videos with captions take about 3 to 6 seconds, mostly for the metadata lookup.
- Videos with no captions are transcribed locally, which takes roughly 1.5 to 2 minutes per 10 minutes of video. `--whisper-model base` is faster but less accurate.

Results are cached in `~/.claude/cache/yt-transcripts/VIDEO_ID.md`, so asking again is instant.

**Long videos:** when a transcript is too long to print, the output shows the metadata, the first part of the transcript and the cache file path. Use Read with offset/limit, or Grep for keywords, on that file instead of printing it all.

## Citing a moment
Link to the timestamp: `https://www.youtube.com/watch?v=VIDEO_ID&t=754s` (the seconds of the `[12:34]` paragraph). Quote only what the transcript actually says. With auto-generated captions, double-check names and numbers against another source before relying on them.

## If it fails
The output lists what each method tried and why it failed. Common causes:
- **Private, removed, members-only or age-restricted videos:** none of these can be fetched.
- **Live streams:** usually have no captions until the stream ends.
- **YouTube rate-limiting:** happens after many requests in a row. Wait a bit, or use fewer videos.

## First-time setup
If `~/.claude/youtube-transcript-env` doesn't exist yet, the main session creates it. The web-researcher agent can't, because its shell only runs the transcript tool. It needs Python 3.11+ and takes about a minute. With [uv](https://docs.astral.sh/uv/):

```bash
uv venv ~/.claude/youtube-transcript-env --python 3.12
```

```bash
uv pip install --python <ENV_PYTHON> -r "${CLAUDE_PLUGIN_ROOT}/skills/youtube-transcript/scripts/requirements.txt"
```

Without uv, create it with `python -m venv ~/.claude/youtube-transcript-env`, then run `<ENV_PYTHON> -m pip install -r` with the same requirements file. The local speech-to-text model (about 0.5 GB) downloads the first time a video without captions is transcribed.

If yt-dlp breaks after a YouTube change, update it:

```bash
uv pip install --python <ENV_PYTHON> -U "yt-dlp[default]"
```

The web-researcher agent can't run these commands. If the tool is missing or broken, it reports the failure instead.
