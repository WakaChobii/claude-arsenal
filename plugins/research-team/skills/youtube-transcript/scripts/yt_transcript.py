"""Fetch a YouTube video's transcript plus the metadata needed to judge it as a source.

Usage (run with the skill's own environment, ~/.claude/youtube-transcript-env):
    python yt_transcript.py URL_OR_ID [URL_OR_ID ...] [--lang en] [--no-whisper] [--whisper-model small]
                                                      [--meta-only] [--refresh]

Tiers, fastest first:
  1. youtube-transcript-api (plain HTTP, about a second)
  2. yt-dlp caption tracks (handles YouTube's PO-token captions)
  3. faster-whisper on the audio, for videos with no captions at all

Metadata (title, channel, upload date, views, duration, description) comes from yt-dlp and is fetched in
parallel with tier 1. Results are cached per video in ~/.claude/cache/yt-transcripts/. Long transcripts are
not printed in full: the full text is saved to the cache file and its path is printed instead.
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "cache", "yt-transcripts")
PRINT_LIMIT = 40000  # characters of transcript printed inline; longer ones are read from the cache file
CHUNK_SECONDS = 30  # one timestamped paragraph per ~30 seconds of speech
ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def video_id(s):
    s = s.strip().strip("\"'")
    if ID_RE.match(s):
        return s
    for pat in (r"[?&]v=([0-9A-Za-z_-]{11})", r"youtu\.be/([0-9A-Za-z_-]{11})",
                r"/(?:shorts|live|embed|v)/([0-9A-Za-z_-]{11})"):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def fmt_ts(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def to_paragraphs(segments):
    """segments: list of (start_seconds, text). Merge into ~30 s timestamped paragraphs."""
    paras, cur, cur_start = [], [], None
    for start, text in segments:
        text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        if not text or text in ("[Music]", "[Applause]"):
            continue
        if cur_start is None:
            cur_start = start
        if cur and cur[-1] == text:  # rolling-caption duplicates
            continue
        cur.append(text)
        if start - cur_start >= CHUNK_SECONDS:
            paras.append((cur_start, " ".join(cur)))
            cur, cur_start = [], None
    if cur:
        paras.append((cur_start, " ".join(cur)))
    return paras


# ---------- metadata ----------

def ydl_opts(**extra):
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True, "noplaylist": True}
    opts.update(extra)
    return opts


def get_info(vid):
    import yt_dlp
    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)


# ---------- tier 1: youtube-transcript-api ----------

def tier1(vid, langs):
    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()
    tl = api.list(vid)
    try:
        tr = tl.find_transcript(langs)
    except Exception:
        tr = next(iter(tl))  # any language; the report says which
    fetched = tr.fetch()
    segs = [(s.start, s.text) for s in fetched]
    kind = "auto-generated captions" if tr.is_generated else "manual captions"
    return segs, f"{kind} ({tr.language_code}) via youtube-transcript-api"


# ---------- tier 2: yt-dlp caption tracks ----------

def pick_track(info, langs):
    for source, label in (("subtitles", "manual captions"), ("automatic_captions", "auto-generated captions")):
        tracks = info.get(source) or {}
        keys = list(tracks)
        wanted = []
        for lang in langs:
            # original-language auto captions first: auto-translated tracks are the ones YouTube rate-limits
            wanted += [k for k in keys if k == f"{lang}-orig"] + [k for k in keys if k == lang] \
                + [k for k in keys if k.startswith(lang + "-") and k != f"{lang}-orig"]
        if source == "automatic_captions" and not wanted:
            wanted = [k for k in keys if k.endswith("-orig")]
        if source == "subtitles" and not wanted:
            wanted = keys[:1]
        for key in wanted:
            fmts = {f.get("ext"): f for f in tracks[key]}
            if "json3" in fmts:
                return fmts["json3"]["url"], f"{label} ({key}) via yt-dlp"
    return None, None


def tier2(vid, langs, info):
    import yt_dlp
    if info is None:
        info = get_info(vid)
    url, label = pick_track(info, langs)
    if not url:
        raise RuntimeError("no caption tracks")
    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        data = json.loads(ydl.urlopen(url).read().decode("utf-8"))
    segs = []
    for ev in data.get("events", []):
        text = "".join(seg.get("utf8", "") for seg in ev.get("segs", []) or [])
        if text.strip():
            segs.append((ev.get("tStartMs", 0) / 1000, text))
    if not segs:
        raise RuntimeError("caption track was empty")
    return segs, label


# ---------- tier 3: faster-whisper ----------

def tier3(vid, model_name):
    import yt_dlp
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    with tempfile.TemporaryDirectory() as tmp:
        opts = ydl_opts(skip_download=False, format="bestaudio[ext=m4a]/bestaudio",
                        outtmpl=os.path.join(tmp, "%(id)s.%(ext)s"))
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
            path = ydl.prepare_filename(info)
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        # batched decoding is several times faster on CPU than sequential transcribe()
        segments, tinfo = BatchedInferencePipeline(model).transcribe(path, batch_size=8, beam_size=1)
        segs = [(s.start, s.text) for s in segments]
    return segs, f"local speech-to-text (faster-whisper {model_name}, language {tinfo.language}); may contain recognition errors"


# ---------- output ----------

def meta_block(vid, info):
    url = f"https://www.youtube.com/watch?v={vid}"
    if not info:
        return f"# YouTube video {vid}\nURL: {url}\n(metadata unavailable)\n"
    d = info.get("upload_date") or ""
    date = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else "unknown"
    views = info.get("view_count")
    subs = info.get("channel_follower_count")
    desc = (info.get("description") or "").strip()
    if len(desc) > 1000:
        desc = desc[:1000] + " [...]"
    lines = [
        f"# {info.get('title', '(untitled)')}",
        f"URL: {url}",
        f"Channel: {info.get('channel') or info.get('uploader') or 'unknown'}"
        + (f" ({subs:,} subscribers)" if subs else "")
        + (" [verified]" if info.get("channel_is_verified") else ""),
        f"Channel URL: {info.get('channel_url') or 'unknown'}",
        f"Uploaded: {date}",
        f"Duration: {fmt_ts(info.get('duration') or 0)}",
        f"Views: {views:,}" if views is not None else "Views: unknown",
    ]
    if info.get("live_status") not in (None, "not_live", "was_live"):
        lines.append(f"Live status: {info.get('live_status')}")
    if info.get("age_limit"):
        lines.append(f"Age limit: {info['age_limit']}")
    lines += ["", "## Description", desc or "(none)"]
    return "\n".join(lines) + "\n"


def process(raw, args):
    vid = video_id(raw)
    if not vid:
        return f"ERROR: could not find a YouTube video ID in {raw!r}\n"
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{vid}.md")
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    if os.path.exists(cache) and not args.refresh and not args.meta_only:
        with open(cache, encoding="utf-8") as f:
            doc = f.read()
        return render(doc, cache, cached=True)

    t0 = time.time()
    errors = []
    with cf.ThreadPoolExecutor(2) as pool:
        info_f = pool.submit(get_info, vid)
        t1_f = None if args.meta_only else pool.submit(tier1, vid, langs)
        try:
            info = info_f.result()
        except Exception as e:
            info = None
            errors.append(f"metadata: {short(e)}")
        if args.meta_only:
            return meta_block(vid, info) + f"(metadata fetched in {time.time() - t0:.1f}s)\n"
        segs = label = None
        try:
            segs, label = t1_f.result()
        except Exception as e:
            errors.append(f"youtube-transcript-api: {short(e)}")

    if segs is None:
        try:
            segs, label = tier2(vid, langs, info)
        except Exception as e:
            errors.append(f"yt-dlp captions: {short(e)}")
    if segs is None and not args.no_whisper:
        dur = (info or {}).get("duration") or 0
        if dur > args.max_whisper_minutes * 60:
            errors.append(f"whisper skipped: video is {fmt_ts(dur)}, longer than --max-whisper-minutes "
                          f"{args.max_whisper_minutes}")
        else:
            print(f"[{vid}] no captions; transcribing audio locally (can take a minute or more)...", file=sys.stderr)
            try:
                segs, label = tier3(vid, args.whisper_model)
            except Exception as e:
                errors.append(f"faster-whisper: {short(e)}")

    head = meta_block(vid, info)
    if segs is None:
        return head + "\n## Transcript\nNOT AVAILABLE. Attempts:\n" + "\n".join(f"- {e}" for e in errors) + "\n"

    body = "\n".join(f"[{fmt_ts(s)}] {t}" for s, t in to_paragraphs(segs))
    doc = (head + f"\n## Transcript\nSource: {label}. Fetched {time.strftime('%Y-%m-%d')} in "
           f"{time.time() - t0:.1f}s. To cite a moment, link {f'https://www.youtube.com/watch?v={vid}'}&t=<seconds>s\n\n"
           + body + "\n")
    with open(cache, "w", encoding="utf-8") as f:
        f.write(doc)
    return render(doc, cache, cached=False)


def render(doc, cache, cached):
    note = f"(cached copy: {cache})\n" if cached else f"(saved to: {cache})\n"
    if len(doc) <= PRINT_LIMIT:
        return note + doc
    head, _, body = doc.partition("\n## Transcript\n")
    return (note + head + "\n## Transcript\n"
            + f"TOO LONG TO PRINT ({len(body):,} characters). The full timestamped transcript is in the file above; "
              f"use Read (with offset/limit) or Grep on it. First part:\n\n" + body[:6000] + "\n[...]\n")


def short(e):
    msg = str(e).strip().splitlines()
    return f"{type(e).__name__}: {msg[0][:200] if msg else ''}"


def main():
    p = argparse.ArgumentParser(description="Fetch YouTube transcripts and metadata.")
    p.add_argument("videos", nargs="+", help="YouTube URLs or 11-character video IDs")
    p.add_argument("--lang", default="en", help="preferred caption languages, comma-separated (default: en)")
    p.add_argument("--meta-only", action="store_true", help="only print metadata (fast vetting before reading)")
    p.add_argument("--no-whisper", action="store_true", help="never fall back to local speech-to-text")
    p.add_argument("--whisper-model", default="small", choices=["tiny", "base", "small", "medium"])
    p.add_argument("--max-whisper-minutes", type=int, default=45)
    p.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = p.parse_args()
    for i, v in enumerate(args.videos):
        if i:
            print("\n" + "=" * 80 + "\n")
        print(process(v, args))


if __name__ == "__main__":
    main()
