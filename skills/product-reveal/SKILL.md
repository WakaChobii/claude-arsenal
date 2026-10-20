---
name: product-reveal
description: Remake the product shots of a reference TikTok (the "product reveal" part - product on a surface, hand holding it, finger pointing at it) with your own product in new rooms and with no on-screen text, using Higgsfield (Kling 3.0 Omni Edit) plus local ffmpeg/OpenCV steps that keep the product label exact. Finds the product shots itself, removes captions, swaps backgrounds and re-assembles them frame-accurately. Use whenever the user gives a reference TikTok (file or link) and wants its product shots/product section/product reveal recreated, remade, copied or "done in new rooms/backgrounds", or says /product-reveal.
---

# Product reveal: remake a TikTok's product shots in new rooms, no text

Input from the user: **a reference TikTok** (a downloaded .mp4), **their product** (an official product photo, or
the product page link) and optionally **backgrounds** (room images). Everything else is decided here. Do every step;
don't stop to ask unless a rule below says to.

This skill's files are in `${CLAUDE_SKILL_DIR}/`:
- `scripts/shots.py`: detect cuts and fades, cut/pad shots, frames, boxes, assemble, check against the reference.
- `scripts/caption_merge.py`: takes the AI's caption-free pixels only inside the caption boxes.
- `scripts/label_patch.py`: puts the real printed label back on close-ups and re-times the AI shot.
- `scripts/setup_check.py`: first-run setup and check.

Needs the **Higgsfield** connector (MCP) for the AI edits. If its tools (`generate_video`, `media_upload`, `balance`)
aren't available, tell the user to connect Higgsfield first and stop.

## Step 0: setup (every time; takes about 2 seconds once it's done)
Run, with whatever `python` / `python3` is on PATH:

```
python "${CLAUDE_SKILL_DIR}/scripts/setup_check.py"
```

- The first run creates a private Python environment in `~/.claude/tiktok-skills/` (shared with add-text) and
  installs the packages (about 1 minute). Tell the user that's what is happening.
- The last line is `READY PY=<path>`. **Use that `<path>` as the python for every command below** (written `PY`).
- `NOT READY: ...` says what's missing and the exact fix. For ffmpeg, ask the user, then run the install command it
  gives. On Windows a new terminal may be needed before ffmpeg is found; if so, tell the user to restart Claude Code.
  No Python 3.9+: the user has to install it (python.org). Then run setup again.
- No `python` command? Try `python3`, or `py` on Windows.

In the commands below, `S` = `${CLAUDE_SKILL_DIR}/scripts`. Quote every path. In PowerShell, start each command with
`& ` (e.g. `& "PY" "S/shots.py" ...`). Work in a scratch folder (e.g. `product reveal work/` next to the reference)
until step 9.

## Rules
- **Credits** (Higgsfield prices when this was written, Oct 2026): about 10.5 credits per product shot (Kling std 4.5
  + Kling pro 6, each on a 3 s clip). Before the first generation, say the shot list and the total (e.g. "3 shots,
  31.5 credits") and go ahead. Anything beyond the plan (a redo, a new room image ~2.75, a resubmit, a test) -> stop
  and ask, with the cost. Check `balance` first; if it can't cover the plan, say so and stop.
- One job per Higgsfield run. Never use Ad Multiplier (`ad_multiplier`) or Ad Multiplier Recreate (`ad_multiplier_v2`).
- If Higgsfield answers with a preset suggestion (e.g. "IN THE DARK") instead of a job, repeat the same call with
  `declined_preset_id` set to that preset's id.
- A job still running after ~15 min: ask before resubmitting (stuck jobs are refunded, a resubmit is charged).
- Output: no text, no sound, the reference's size (TikTok: 1080x1920) at 30 fps. Check it against the reference before
  calling it done.
- The result is AI-edited video. Tell the user that TikTok requires its **AI-generated content label** when posting.

Why the method looks like this: every AI video edit redraws the whole frame and garbles small print, and multi-shot
edits drop short shots and move cuts. So each shot is edited on its own, captions are taken from Kling only inside
the caption boxes, and on close-ups the real label is put back from the original.

## 1. Find the product shots
- `"PY" "S/shots.py" detect "<reference>" "<scratch>"` prints fps, frame count, every cut (frame numbers) and fades,
  and writes `<scratch>/_sheet.png` (a tile every 5 frames, numbered). Look at the sheet.
- Need to download the reference first? `yt-dlp` works if it's installed. Otherwise ask the user for the file.
- The product shots = the shots where the product is the subject (on a surface, held up, pointed at, applied,
  unboxed). Skip hooks, faces, before/afters, results. Usually one continuous section; take all of it.
- For each product shot note: first/last frame (cut frames from detect; a shot ends one frame before the next cut),
  CLOSE-UP (product big, label readable) or FAR, its captions word for word, and whether captions switch one frame
  early (check the frames at each cut with `shots.py frame`). Note fades into/out of the section (detect lists them):
  skip frames that are mid-fade and rebuild the fade in step 8.
- The user's product should be the same kind of packaging as the one in the reference (tube for tube, jar for jar).
  If it clearly isn't, say so and ask before spending credits.

## 2. Product photo
- Use the photo the user gave (the largest official packshot matching the packaging). If they gave a product page
  link instead, take the largest gallery image from it and save it next to the reference.
- Paint out anything that isn't the product (gift boxes, "Free" badges) with white (ffmpeg drawbox), view it.
- Upload once (`media_upload`, curl PUT, `media_confirm`) and write the id in a `higgsfield ids.txt` next to the photo,
  so it can be reused next time.

## 3. Backgrounds
- If the user gave rooms, upload and use them. Look at them first: top-down surface for flat-lays, angled room for a
  hand holding the product.
- If they gave none, or nothing fits, ask before making one (~2.75 credits): take a frame of the reference (or of a
  room photo the user likes), `generate_image` gpt_image_2_5, high, 2k, 9:16, "remove the hands, products and all
  text (and their reflections), keep everything else, fill the cleared area, photoreal phone look". Save it with the
  results so it can be reused.

## 4. Cut each shot (from the reference, full resolution)
- `"PY" "S/shots.py" cut "<reference>" FIRST END "<scratch>/shotN.mp4"` (END = last frame + 1).
- `"PY" "S/shots.py" pad "<scratch>/shotN.mp4" "<scratch>/shotN_3s.mp4"` (forward-backward-forward to 90 frames;
  Kling needs >= 3 s). Shots already >= 3 s stay as they are.

## 5. Remove captions (Kling std, ~4.5 credits per 3 s shot)
- Upload each padded shot (`media_upload`, curl PUT, `media_confirm`; batch the uploads). `generate_video` model
  `kling_video_edit`, mode `std`, media role `video_references`. Run all shots in parallel. Prompt:
  "Remove all the on-screen text overlays and emojis from the video: '<text 1>', '<text 2>', ... Fill the areas
  behind the text so they match their surroundings. Keep everything else exactly the same: the <product> and its
  printed label, the <hand/finger> and its motion, the <surface/background>, the <props>, the camera movement,
  lighting and timing."
- Measure each caption box on a full-size frame (`shots.py frame`), pad ~15 px, include emojis, and DRAW them
  (`shots.py boxes`) to check. TikTok captions don't move, so one box per caption, active for the shot's frames.
- `"PY" "S/caption_merge.py" "<scratch>/shotN.mp4" kling_notext.mp4 "<scratch>/shotN_clean.mp4" "x,y,w,h,first,last" ...`
  (frames 0-based within the shot). Outside the boxes everything stays the original full-resolution pixels.
- If the shot's last frame already shows the next shot's caption: `shots.py holdlast` on the clean shot.
- Check a few frames and zoom on the box edges (no seams), then `shots.py pad` the clean shot to 3 s and upload it.

## 6. Swap the background (Kling pro, ~6 credits per 3 s shot, 1080p out)
- `generate_video` model `kling_video_edit`, mode `pro`. Medias: clean padded shot (`video_references`), room image
  (`image_references`, @Image1), product photo (`image_references`, @Image2). All shots in parallel. Prompt:
  "Edit only the <background|surface> of this video. @Image1 is <room description>. @Image2 is the official photo of
  the product, the <product>. Replace only the <blurred room behind the hand and the product | <old surface>> with
  the <room> from @Image1<, softly blurred like a phone camera's background>, for the whole video. Keep <the props>
  exactly where they are. Keep the <product> exactly as it is in the video, like @Image2: its shape, colours, logo and
  printed label. Keep the <hand/finger> and its motion, the product's position, the camera movement, the lighting and
  the timing exactly the same as the source video."
- Check a 3-frame sheet of each: right room, product intact, hand/finger intact, no extra objects.

## 7. Label (free, local)
- CLOSE-UP shots: draw a rectangle around the printed words on frame 0 of the clean shot (inside the product, margin
  of plain packaging around the text, off the fingers; check it with `shots.py boxes`), then
  `"PY" "S/label_patch.py" "<scratch>/shotN_clean.mp4" kling_swap.mp4 "<scratch>/shotN_final.mp4" x,y,w,h`.
  Compare a full-size label crop: original vs Kling vs patched.
- FAR shots: same command with `--no-patch` (Kling's frames re-timed to the original; the rectangle still goes on the
  product, for timing). Never patch small products: it looks like a pasted cutout.
- Both commands print "AI frames per original frame": about 0.8 is right (Kling outputs 24 fps).

## 8. Assemble and check
- `"PY" "S/shots.py" assemble "<scratch>/section.mp4" shot1_final.mp4 shot2_final.mp4 ... [--hold K --fade N]`
  `--hold/--fade` rebuild a fade up from black at the start (K = mid-fade frames skipped in step 1, N = fade length).
- `"PY" "S/shots.py" check "<scratch>/section.mp4" "<reference>" START END "<scratch>"` (START/END = the section's
  frames in the reference, including skipped fade frames): frame counts and cuts must match. Look at `_compare.png`.
- Reference-audio check copy: `ffmpeg -i section.mp4 -ss <START/fps> -i "<reference>" -map 0:v -map 1:a -c:v copy -c:a aac -shortest "...DON'T POST.mp4"`.

## 9. Save
Into a folder next to the reference, `<product> product reveal - <creator>/` (creator from the file name or the
watermark, else "unknown"):
- `<product> product reveal (no text) (no sound).mp4` - the section
- `<product> product reveal (reference audio) - DON'T POST.mp4` - for checking sync only
- `shots/` - each shot on its own, named `<product>_<shot>_<setting>_<camera move>_AI_<NN>.mp4`
  (e.g. `mudmask_hand-holds-tube-up_grey-vanity-blurred_handheld_AI_01.mp4`)
- `_overview.png` (the `_compare.png`), `reference/` (the reference TikTok, a label close-up of each close-up shot)
- `what is in here.txt`: shots with frames/times and CLOSE-UP/FAR, rooms used, files, method, known flaws, credits
  spent (check `transactions`), every Higgsfield job id.

Then delete the scratch files. Show the user the overview, say where the video is and the credits spent, and remind
them about TikTok's AI-generated label. To add TikTok-style captions to the result, use the add-text skill.
