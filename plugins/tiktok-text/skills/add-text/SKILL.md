---
name: add-text
description: Burn on-screen text onto a video so it looks exactly like TikTok's own in-app text tool (TikTok Sans "Classic" font; plain white, white with black outline, pale yellow, gold yellow, lilac; Apple iPhone emoji) - either copying the captions of a reference TikTok frame-accurately (wording, line breaks, size, position, timing) or writing new captions. Use whenever the user asks to add text, captions, an overlay or a hook to a video, to copy/recreate a reference video's text, or says "with text".
---

# Add TikTok-style text to a video

This skill's files are in `${CLAUDE_PLUGIN_ROOT}/skills/add-text/`:
- `scripts/add_text.py`: **use this.** It runs the whole job in two commands.
- `scripts/caption_match.py` (detect / fit / check) and `scripts/tiktok_text.py` (draws + burns): the engine.
- `scripts/setup_check.py`: first-run setup and check.
- `fonts/`: TikTok Sans (open source, OFL licence).

The styles were measured against real in-app TikToks. **Don't render text any other way** (ffmpeg drawtext, a
plain font, etc.). It won't match.

## Step 0: setup (every time; takes about 2 seconds once it's done)
Run, with whatever `python` / `python3` is on PATH:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/add-text/scripts/setup_check.py" "${CLAUDE_PLUGIN_DATA}"
```

- The first run creates a private Python environment in the plugin's data folder and installs the packages
  (about 1-2 minutes). Tell the user that's what is happening.
- The last line is `READY PY=<path>`. **Use that `<path>` as the python for every command below** (written `PY`).
- `NOT READY: ...` says what's missing and the exact fix:
  - **ffmpeg**: ask the user, then run the install command it gives (`winget` on Windows, `brew` on Mac, `apt` on
    Linux). On Windows, a new terminal may be needed before ffmpeg is found. If so, tell the user to restart
    Claude Code.
  - **No Python 3.9+**: the user has to install it (python.org) and restart Claude Code.

  Then run setup again.
- No `python` command? Try `python3`, or `py` on Windows.

In the commands below, `S` = `${CLAUDE_PLUGIN_ROOT}/skills/add-text/scripts`. Quote every path. In PowerShell, start
each command with `& ` (e.g. `& "PY" "S/add_text.py" ...`).

## Rules
- Output stays the input video's size and frame rate (TikTok: 1080x1920). Save the text version next to the
  original as `<name> (WITH TEXT).mp4`, and never overwrite the original.
- **Content:** TikTok penalises misleading claims. Avoid absolute result claims ("cured", "fixed in 3 days",
  "guaranteed"). When a reference's hook makes a claim, adapt the wording (same rhythm and line count), and tell
  the user what you changed and why. Ask if unsure.
- Typed text must be what an iPhone would produce:
  - `…` not `...`
  - curly quotes `’` `“ ”` if the reference uses them
  - emoji as the real emoji characters
- Leading and trailing spaces matter: TikTok centres each line including its spaces. `fit` adds them for you.

## A. Copying a reference TikTok's text
Use a work folder next to the user's video, e.g. `text work/`.

1. **Start:** `"PY" "S/add_text.py" start "REF.mp4" "WORKDIR"`
   - Prints every caption: start/end (frame-accurate, reference timeline), style, fill colour and box.
   - Writes `WORKDIR/captions.json` with `"text": "??"`, and a zoomed crop `WORKDIR/caption_<n>.png` of each.
   - It skips TikTok's own "TikTok @user" watermark.
   - Need to download the reference first? `yt-dlp` works if it's installed. Otherwise ask the user for the file.
2. **Fill in the text.** Read each crop image and replace each `"??"`.
   - Leave the other fields. The `_` ones (`_ref_t`, `_bbox_1080`, ...) are used by finish.
   - Line breaks are `\n`, and emoji are characters. Don't worry about leading or trailing spaces.
   - If two lines are about twice the normal spacing apart, that's a blank line: `"A\n\nB"`.
   - Two separate text boxes in one caption (very different sizes, a big gap, or not centred on the same x): split
     them into two entries with the same start/end, `_ref_t` and style. Give each its own `_bbox_1080`: the union
     of its lines from `_lines_1080` (detect prints each line's box and height), so fit looks at the right text.
     Example: lines 1:[346,1126,735,1167] and 2+3 → `[346,1126,735,1167]` and `[204,1272,887,1389]`.
   - `style` came back `custom` / `custom_outline`? That's another font, a background box or another colour,
     which this tool doesn't have. Tell the user and pick the closest style. Don't guess silently.
   - **Retime here** if the user's cuts differ from the reference: edit `start`/`end` (seconds, end exclusive).
     Fit and check still look at the reference at its own time (`_ref_t`).
3. **Finish:** `"PY" "S/add_text.py" finish "REF.mp4" "VIDEO.mp4" "WORKDIR"`
   - Fits size, position and spaces into the json, and writes `WORKDIR/fit_<n>.png` (reference on top, ours below).
   - Ends any caption that runs past the video at the video's length.
   - Burns `VIDEO (WITH TEXT).mp4` next to the video (or `(no text)` → `(WITH TEXT)`). A 4th argument picks
     another output name.
   - Checks the result and writes `WORKDIR/check.jpg` (reference left, ours right).
   - Prints a **SUMMARY: PASS or REVIEW** with the reasons.
4. **Look** at `check.jpg` and show it to the user before saying it's done.
   - Low overlap with **"edges match the reference within N px"**: size and position are right. Compressed gold or
     yellow text often scores 0.45-0.7 even when it's correct. Just confirm the wording by eye.
   - Low overlap with **"edges off by N px"**: usually a typo, a missed line break, the wrong style, or a bad
     `_bbox_1080` after a split. Fix the json and re-run finish.
   - To keep hand-tuned size/y/x, add `--no-fit`.

## B. New captions (no reference)
Write a `captions.json`:

```json
[{"text": "line one\nline two", "start": 0, "end": 3.5, "style": "outline", "size": 70, "y": 0.5}]
```

Then run `"PY" "S/add_text.py" new "VIDEO.mp4" "WORKDIR/captions.json"`. It burns the text and writes
`preview.jpg` (one frame per caption) next to the json. Show it to the user.

- **style:** `classic` (plain white), `outline` (white + black outline), `yellow` (pale), `yellow_gold`, `lilac`.
- **size:** about 50 (small) to 85 (big). Typical hooks are 54-77.
- **y:** 0.4-0.5 = middle of the screen, 0.65 = lower third. Keep clear of the bottom 20% (TikTok's caption/UI)
  and the right edge (buttons).
- **Optional:** `x` (horizontal centre, default 0.5), `weight`, `color` ("#RRGGBB" for a custom fill).
- Break lines where a person typing on a phone would. Lines are about 20-28 characters at size 70.

Quick look without rendering a video: `"PY" "S/tiktok_text.py" --png "text\nmore" out.png` (classic style).

## Gotchas
- Typical timings: start about 25 s, finish 1-3 min depending on the number of captions (outline captions fit
  slowest), `--no-fit` about 40 s.
- Emoji: each new one downloads once (Apple set, emoji-data CDN on jsDelivr), so it needs internet the first time.
  If a download fails the script raises. Tell the user rather than dropping the emoji.
- No shadow, on purpose: real TikTok text has none. The "cleaner" look next to the compressed reference is expected
  and goes away once TikTok re-encodes the upload.
- With only 2 lines, fit's space fixer can't tell which line is off-centre. If `fit_<n>.png` shows one line shifted
  about 5 px and overlap stays below about 0.6, try a trailing or leading space on each line yourself and re-run.
- Windows: if emoji print oddly in other Python snippets, set `PYTHONIOENCODING=utf-8`. These scripts handle it.
