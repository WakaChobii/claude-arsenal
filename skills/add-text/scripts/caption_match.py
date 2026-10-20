"""Copy the on-screen captions of a reference TikTok onto our own video, fast and checked.

  1. python caption_match.py detect REF.mp4 OUTDIR
       Finds every caption in the reference: when it is on screen (frame-accurate), its style
       (classic / outline / yellow / yellow_gold / custom colour) and where it sits. Writes
       OUTDIR/captions.json (text = "??") and OUTDIR/caption_<n>.png zoomed crops so you can read the exact
       wording, line breaks, trailing spaces and emoji.
  2. Fill in "text" in captions.json (use "\\n" for line breaks, "…" not "...", emoji as the real emoji).
  3. python caption_match.py fit REF.mp4 OUTDIR/captions.json
       Fits each caption's font size and vertical position to the reference (overwrites size/y in the json)
       and writes OUTDIR/fit_<n>.png: reference crop on top, our rendering below.
  4. python tiktok_text.py OUR_VIDEO.mp4 OUT.mp4 OUTDIR/captions.json      (burns the text in)
  5. python caption_match.py check REF.mp4 OUT.mp4 OUTDIR/captions.json
       Compares on/off frames and the text masks of reference vs result, writes OUTDIR/check.jpg.

Times are seconds on the REFERENCE timeline. If our video's timing differs, shift start/end before burning.
Only TikTok's in-app "Classic" font styles are supported (see tiktok_text.STYLES); other fonts / boxed text are
reported as "custom" and need a new style measured first.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_erosion, label

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiktok_text as tt

W, H = 1080, 1920
SW, SH = 540, 960                      # analysis scale (half res) for scanning


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                          "stream=r_frame_rate,nb_read_frames", "-of", "json", path], capture_output=True, text=True)
    st = json.loads(out.stdout)["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return float(num) / float(den), int(st["nb_read_frames"])


def frames(path, w=SW, h=SH):
    """Yield every frame (RGB uint8, w x h)."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.wait()


def frame_at(path, t, w=W, h=H):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf",
                          f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def text_colour_mask(a):
    """Pixels that could be caption fill: near-white, TikTok yellows or TikTok lilac."""
    a = a.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    white = a.min(axis=2) > 225
    yellow = (r > 190) & (g > 140) & (b < 185) & (r - b > 45) & (g > b + 30)
    lilac = (r > 215) & (b > 215) & (g > 160) & (g < 225) & (r - g > 22) & (b - g > 22)
    return white | yellow | lilac


def caption_components(m):
    """Keep blobs shaped like letters and lying in a few horizontal text bands."""
    lab, n = label(m)
    keep = np.zeros_like(m)
    if n == 0:
        return keep
    sl = __import__("scipy.ndimage", fromlist=["find_objects"]).find_objects(lab)
    comps = []
    for i, s in enumerate(sl, 1):
        h, w = s[0].stop - s[0].start, s[1].stop - s[1].start
        area = (lab[s] == i).sum()
        if 3 <= h <= 60 and w <= 120 and 6 <= area <= 3000 and area / (h * w) > 0.12:
            comps.append((s[0].start, s[0].stop, s[1].start, s[1].stop, i))
    # group letters into text lines: vertical overlap + small horizontal gaps
    lines = []
    for c in sorted(comps, key=lambda c: c[2]):
        cy = (c[0] + c[1]) / 2
        for ln in lines:
            if ln["y0"] - 4 <= cy <= ln["y1"] + 4 and c[2] - ln["x1"] < 3 * (ln["y1"] - ln["y0"]) + 6:
                ln["c"].append(c); ln["y0"] = min(ln["y0"], c[0]); ln["y1"] = max(ln["y1"], c[1])
                ln["x1"] = max(ln["x1"], c[3]); break
        else:
            lines.append({"c": [c], "y0": c[0], "y1": c[1], "x0": c[2], "x1": c[3]})
    # >= 4 letters, and letters at least ~9 px tall at half res (smaller = TikTok's own "TikTok @user" watermark)
    good = [ln for ln in lines if len(ln["c"]) >= 4 and ln["x1"] - ln["x0"] >= 40
            and np.median([c[1] - c[0] for c in ln["c"]]) >= 9]
    # short lines (e.g. "ts 😭") count if they sit right under/over a good line
    for ln in lines:
        if ln not in good and len(ln["c"]) >= 2 and any(abs(ln["y0"] - g["y1"]) < 2.5 * (g["y1"] - g["y0"]) or
                                                        abs(g["y0"] - ln["y1"]) < 2.5 * (g["y1"] - g["y0"]) for g in good):
            good.append(ln)
    for ln in good:
        for y0, y1, x0, x1, i in ln["c"]:
            keep[y0:y1, x0:x1] |= lab[y0:y1, x0:x1] == i
    return keep


def _line_boxes(m):
    """[x0, y0, x1, y1] (1080x1920 coords) of each text line in a half-res mask, top to bottom. Bands split only by
    i-dots/accents (gap <= 4 px at half res) are joined."""
    rows = np.append(m.sum(axis=1) > 2, False)
    bands, s = [], None
    for y, v in enumerate(rows):
        if v and s is None:
            s = y
        elif not v and s is not None:
            if bands and s - bands[-1][1] <= 4:
                bands[-1][1] = y
            else:
                bands.append([s, y])
            s = None
    out = []
    for y0, y1 in bands:
        if y1 - y0 < 4:
            continue
        xs = np.where(m[y0:y1].any(axis=0))[0]
        out.append([int(xs.min() * 2), int(y0 * 2), int(xs.max() * 2 + 1), int(y1 * 2 - 1)])
    return out


def detect(ref, outdir):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    fps, nfr = probe(ref)
    # 1. stable text-coloured pixels over a short window (captions don't move, footage does)
    win, step = max(2, round(fps * 0.25)), max(1, round(fps * 0.25))
    buf, samples = [], []
    for i, f in enumerate(frames(ref)):
        buf.append(text_colour_mask(f))
        if len(buf) > win:
            buf.pop(0)
        if len(buf) == win and i % step == 0:
            stable = np.logical_and.reduce(buf)
            comp = caption_components(stable)
            if comp.sum() > 80:
                samples.append((i - win + 1, comp))
    # 2. group samples into captions (same pixels), master mask = pixels present in most samples
    caps = []
    for i0, m in samples:
        for c in caps:
            core = c["acc"] >= c["n"] * 0.5
            if (core & m).sum() / max(1, (core | m).sum()) > 0.5:
                c["acc"] += m; c["n"] += 1; break
        else:
            caps.append({"acc": m.astype(np.int32), "n": 1})
    caps = [c for c in caps if c["n"] >= 2]
    # Masters: text in >= 80% of a group's samples, plus text present for only part of the group (>= 30%) away
    # from that master - a second caption that pops in while the first is on screen (e.g. "On sale rn 👇" under
    # "This is what helped me") would otherwise fall under the 80% bar and be lost. Step 3 times it on its own.
    masters = []
    for c in caps:
        main = caption_components(c["acc"] >= max(1, c["n"] * 0.8))
        masters.append(main)
        extra = caption_components((c["acc"] >= max(2, c["n"] * 0.3)) & ~binary_dilation(main, iterations=6))
        if extra.sum() >= 50 and main.any():
            my, ey = np.where(main)[0], np.where(extra)[0]
            gap = max(ey.min() - my.max(), my.min() - ey.max())   # half-res px between the two blocks
            if gap > 30:                                         # touching/near = flicker in the same caption
                masters.append(extra)
    # 3. frame-accurate on/off per caption + style
    out = []
    for master in masters:
        if master.sum() < 50:
            continue
        pres, cols, whites, ring_l, outer_l = [], [], [], [], []
        ring = binary_dilation(master, iterations=3) & ~binary_dilation(master, iterations=1)
        outer = binary_dilation(master, iterations=8) & ~binary_dilation(master, iterations=6)
        core = binary_erosion(master, iterations=1)
        if core.sum() < 20:
            core = master
        for f in frames(ref):
            tm = text_colour_mask(f)
            on = tm[master].mean() > 0.75
            pres.append(on)
            if on:
                cols.append(np.median(f[core], axis=0))
                whites.append((f[core].min(axis=1) > 220).mean())
                ol = np.median(f[outer].mean(axis=1))
                if ol > 90:                                  # only frames with a bright-ish background tell
                    ring_l.append(np.median(f[ring].mean(axis=1))); outer_l.append(ol)
        pres = np.array(pres)
        idx = np.where(pres)[0]
        if len(idx) == 0:
            continue
        # longest run of presence (bridging gaps of <= 2 frames, e.g. dips to black are text-on anyway)
        runs, s, prev = [], idx[0], idx[0]
        for k in idx[1:]:
            if k - prev > 3:
                runs.append((s, prev)); s = k
            prev = k
        runs.append((s, prev))
        for a, b in runs:
            if b - a < fps * 0.3:
                continue
            col = np.median(np.array(cols), axis=0).astype(int)
            outline = bool(ring_l) and float(np.median(ring_l)) < 60 and np.median(outer_l) - np.median(ring_l) > 40
            style = _style_for(col, outline)
            if style == "custom_outline" and np.median(whites) > 0.3:
                style = "outline"                            # white letters; a big coloured emoji skewed the median
                col = np.array([255, 255, 255])              # ("On sale rn 👇": emoji = half the pixels)
            if style.startswith("custom") and (b - a + 1) / fps < 1.0:
                continue                                     # brief odd-coloured blob = background, not a caption
            ys, xs = np.where(master)
            # times half-way between frames, so rounding / other frame rates can't add or drop a frame
            out.append({"text": "??", "start": round(max(0, (a - 0.5) / fps), 3), "end": round((b + 0.5) / fps, 3), "style": style,
                        "_frames": [int(a), int(b)], "_ref_t": round((a + b + 1) / 2 / fps, 3), "_fill_rgb": col.tolist(),
                        "_bbox_1080": [int(xs.min() * 2), int(ys.min() * 2), int(xs.max() * 2 + 1), int(ys.max() * 2 + 1)],
                        "_lines_1080": _line_boxes(master)})
    out = [c for c in out if not _is_watermark(ref, c)]
    out.sort(key=lambda c: (c["start"], c["_bbox_1080"][1]))
    # 4. zoomed crops for reading the text
    for n, c in enumerate(out, 1):
        t = (c["start"] + c["end"]) / 2
        a = frame_at(ref, t)
        x0, y0, x1, y1 = c["_bbox_1080"]
        pad = 40
        crop = Image.fromarray(a).crop((max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)))
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        crop.save(outdir / f"caption_{n}.png")
        c["_crop"] = f"caption_{n}.png"
    (outdir / "captions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} caption(s) at {fps:g} fps -> {outdir/'captions.json'}")
    for n, c in enumerate(out, 1):
        print(f"  {n}. {c['start']:.3f}-{c['end']:.3f}s  style={c['style']}  fill={c['_fill_rgb']}  box={c['_bbox_1080']}  crop={c['_crop']}")
        if len(c["_lines_1080"]) > 1:
            print("       lines (x0,y0,x1,y1; height): " + "  ".join(
                f"{i}:{b} h{b[3] - b[1]}" for i, b in enumerate(c["_lines_1080"], 1)))


def _is_watermark(ref, c):
    """TikTok's own "TikTok @user" overlay: white text next to the cyan + red logo."""
    a = frame_at(ref, (c["start"] + c["end"]) / 2).astype(np.int16)
    x0, y0, x1, y1 = c["_bbox_1080"]
    r = a[max(0, y0 - 40):y1 + 40, max(0, x0 - 160):x1 + 40]
    cyan = ((r[..., 1] > 170) & (r[..., 2] > 170) & (r[..., 0] < 120)).sum()
    red = ((r[..., 0] > 190) & (r[..., 1] < 90) & (r[..., 2] > 40) & (r[..., 2] < 160)).sum()
    return cyan > 20 and red > 20


def _style_for(rgb, outline):
    r, g, b = rgb
    if outline:
        return "outline" if min(rgb) > 220 else "custom_outline"
    cand = {"classic": (255, 255, 255), "yellow": tt._rgb(tt.STYLES["yellow"]["color"]),
            "yellow_gold": tt._rgb(tt.STYLES["yellow_gold"]["color"]), "lilac": tt._rgb(tt.STYLES["lilac"]["color"])}
    best = min(cand, key=lambda k: np.abs(np.array(cand[k], float) - rgb).sum())
    return best if np.abs(np.array(cand[best], float) - rgb).sum() < 40 else "custom"


def style_colour_mask(a, style):
    """Pixels in this style's own fill colour: white for classic/outline, the yellow/lilac band for those. Keeps a
    coloured emoji (👇 is yellow) out of a white caption's mask, so fit sizes on the letters, not the emoji."""
    m = text_colour_mask(a)
    white = a.min(axis=2) > 225
    if style in ("classic", "outline"):
        return m & white
    if style in ("yellow", "yellow_gold"):                 # TikTok yellows have G close to R (pale 0.98, gold 0.84);
        a16 = a.astype(np.int16)                           # peach skin (~0.75) otherwise passes as yellow
        return m & ~white & (a16[..., 1] * 100 > a16[..., 0] * 80)
    if style == "lilac":
        return m & ~white
    return m


def _ref_mask(a, style, box=None):
    m = style_colour_mask(a, style)
    if style == "outline":                                  # white enclosed by the black stroke
        dark = a.max(axis=2) < 90
        lab, n = label(m)
        keep = np.zeros_like(m)
        for i in range(1, n + 1):
            c = lab == i
            if c.sum() < 15:
                continue
            border = binary_dilation(c, iterations=3) & ~binary_dilation(c, iterations=1)
            if dark[border].mean() > 0.8:
                keep |= c
        m = keep
    if box is not None:
        x0, y0, x1, y1 = box
        bm = np.zeros_like(m); bm[max(0, y0 - 30):y1 + 30, max(0, x0 - 30):x1 + 30] = True
        m &= bm
    return m


def _our_mask(img, style=None):
    A = np.asarray(img)
    return (A[..., 3] > 200) & style_colour_mask(A[..., :3], style)


def _fit_one(R, text, style, sizes=None):
    """Best (overlap, size, dx, dy) of our rendering against reference mask R."""
    ry, rx = np.where(R)
    if sizes is None:                                       # first guess: scale a size-70 render to the ref height
        gy, _ = np.where(_our_mask(tt.caption_png(text, style, size=70, y=0.5), style))
        size0 = 70 * (ry.max() - ry.min()) / max(1, gy.max() - gy.min())
        sizes = np.round(np.arange(size0 * 0.95, size0 * 1.051, size0 * 0.0125) * 4) / 4
    best = None
    for size in sizes:
        m = _our_mask(tt.caption_png(text, style, size=size, y=0.5), style)
        y, x = np.where(m)
        dx0 = int(round((rx.min() + rx.max()) / 2 - (x.min() + x.max()) / 2)); dy0 = int(round(ry.min() - y.min()))
        for dy in range(dy0 - 3, dy0 + 4):
            for dx in range(dx0 - 4, dx0 + 5):
                M = np.roll(np.roll(m, dy, 0), dx, 1)
                iou = (M & R).sum() / (M | R).sum()
                if best is None or iou > best[0]:
                    best = (iou, float(size), dx, dy)
    return best


def _line_centres(m):
    """Horizontal centre of each text line (top to bottom) in a mask."""
    rows = m.sum(axis=1) > 2
    out, inb = [], False
    for y, v in enumerate(np.append(rows, False)):
        if v and not inb:
            s, inb = y, True
        elif not v and inb:
            inb = False
            if y - s > 6:
                xs = np.where(m[s:y].any(axis=0))[0]; out.append(((s + y) / 2, (xs.min() + xs.max()) / 2))
    merged = []                                             # join bands split by descenders/accents
    for c in out:
        if merged and c[0] - merged[-1][0] < 20:
            continue
        merged.append(c)
    return [x for _, x in merged]


def _fix_spaces(R, text, style, best):
    """Spaces are invisible in a crop but TikTok centres each line including them. If one line of a multi-line
    caption is off-centre relative to the others by about half a space, add a trailing (moves it left) or leading
    (moves it right) space and keep it if the fit improves. Returns (text, best, notes)."""
    notes, lines = [], text.split("\n")
    if len([l for l in lines if l.strip()]) < 2:
        return text, best, notes
    for _ in range(len(lines)):
        iou, size, dx, dy = best
        m = np.roll(np.roll(_our_mask(tt.caption_png(text, style, size=size, y=0.5), style), dy, 0), dx, 1)
        rc, oc = _line_centres(R), _line_centres(m)
        if len(rc) != len(oc):
            break
        d = np.array(rc) - np.array(oc)
        sw = tt.ImageFont.truetype(tt.app_font(575), int(size * 4)).getlength(" ") / 4
        rel = d - np.median(d)
        k = int(np.argmax(np.abs(rel)))
        if abs(rel[k]) < 0.3 * sw:
            break
        nonblank = [i for i, l in enumerate(lines) if l.strip()]
        li = nonblank[k]
        trial = list(lines)
        trial[li] = trial[li] + " " if rel[k] < 0 else " " + trial[li]
        tbest = _fit_one(R, "\n".join(trial), style, sizes=[size - 0.25, size, size + 0.25])
        if tbest[0] <= iou + 0.01:
            break
        lines, text, best = trial, "\n".join(trial), tbest
        notes.append(f"added a {'trailing' if rel[k] < 0 else 'leading'} space to line {li + 1}")
    return text, best, notes


def fit(ref, cap_json):
    cap_json = Path(cap_json); outdir = cap_json.parent
    caps = json.loads(cap_json.read_text(encoding="utf-8"))
    for n, c in enumerate(caps, 1):
        if "??" in c["text"]:
            print(f"  {n}: text not filled in - skipped"); continue
        t = c.get("_ref_t", (c["start"] + c["end"]) / 2)   # reference timeline, even after start/end are retimed
        a = frame_at(ref, t)
        R = _ref_mask(a, c["style"], c.get("_bbox_1080"))
        if R.sum() < 50:
            print(f"  {n}: reference text not found at {t:.2f}s - skipped"); continue
        ry, rx = np.where(R)
        best = _fit_one(R, c["text"], c["style"])
        c["text"], best, notes = _fix_spaces(R, c["text"], c["style"], best)
        for note in notes:
            print(f"  {n}: {note} (TikTok centres lines including spaces)")
        iou, size, dx, dy = best
        c["size"], c["y"] = size, round(0.5 + dy / H, 5)
        c["_fit_overlap"] = round(float(iou), 3)
        if abs(dx) >= 2:                                    # text was dragged off-centre in the app
            c["x"] = round(0.5 + dx / W, 5)
        else:
            c.pop("x", None)
        img = tt.caption_png(c["text"], c["style"], size=size, y=c["y"], x=c.get("x"))
        x0, y0, x1, y1 = c.get("_bbox_1080", [0, int(ry.min()), W, int(ry.max())])
        box = (max(0, x0 - 60), max(0, y0 - 60), min(W, x1 + 60), min(H, y1 + 60))
        import cv2                                          # erase the real text, then draw ours
        hole = binary_dilation(R | binary_dilation(text_colour_mask(a), iterations=1) & binary_dilation(R, iterations=25), iterations=8)
        bg = cv2.cvtColor(cv2.inpaint(cv2.cvtColor(a, cv2.COLOR_RGB2BGR), hole.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
        ours = Image.alpha_composite(Image.fromarray(bg).convert("RGBA"), img).convert("RGB")
        top = Image.fromarray(a).crop(box); bot = ours.crop(box)
        sheet = Image.new("RGB", (top.width, top.height * 2 + 8), "white")
        sheet.paste(top, (0, 0)); sheet.paste(bot, (0, top.height + 8)); sheet.save(outdir / f"fit_{n}.png")
        print(f"  {n}: size {size}  y {c['y']}" + (f"  x {c['x']} (off-centre {dx:+d}px)" if "x" in c else "")
              + f"  letter overlap {iou:.2f}  (good: >0.75 on a 1080p reference)  -> fit_{n}.png")
    cap_json.write_text(json.dumps(caps, indent=1, ensure_ascii=False), encoding="utf-8")


def check(ref, ours, cap_json):
    caps = json.loads(Path(cap_json).read_text(encoding="utf-8"))
    outdir = Path(cap_json).parent
    fps_r, _ = probe(ref); fps_o, n_o = probe(ours)
    dur_o = n_o / fps_o
    rows, results = [], []
    for n, c in enumerate(caps, 1):
        mid = (c["start"] + c["end"]) / 2
        if c["end"] > dur_o + 0.05:
            print(f"  {n}: WARNING caption runs to {c['end']:.2f}s but our video is only {dur_o:.2f}s long"
                  + (" - not checked" if mid >= dur_o else ""))
            if mid >= dur_o:
                continue
        a, b = frame_at(ref, c.get("_ref_t", mid)), frame_at(ours, mid)
        Rm, Om = _ref_mask(a, c["style"], c.get("_bbox_1080")), _ref_mask(b, c["style"], c.get("_bbox_1080"))
        iou = (Rm & Om).sum() / max(1, (Rm | Om).sum())
        # on/off frames in our video, using our own mask at mid
        Oh = binary_erosion(Om[::2, ::2], iterations=1)
        on = [bool(Oh.sum()) and text_colour_mask(f)[Oh].mean() > 0.75 for f in frames(ours)]
        idx = np.where(on)[0]
        want = (int(np.ceil(c["start"] * fps_o - 1e-6)), int(np.ceil(c["end"] * fps_o - 1e-6)) - 1)
        got = (int(idx[0]), int(idx[-1])) if len(idx) else None
        ok = got is not None and abs(got[0] - want[0]) <= 1 and abs(got[1] - want[1]) <= 1
        print(f"  {n}: text overlap ref vs ours {iou:.2f} (good: >0.75) | frames on: wanted {want[0]}-{want[1]}, "
              f"ours {got[0] if got else None}-{got[1] if got else None} at {fps_o:g} fps " + ("OK" if ok else "<-- MISMATCH"))
        box_err = None                                      # how far the text block's edges are apart (px)
        if Rm.any() and Om.any():
            (ry, rx), (oy, ox) = np.where(Rm), np.where(Om)
            box_err = int(max(abs(ry.min() - oy.min()), abs(ry.max() - oy.max()), abs(rx.min() - ox.min()), abs(rx.max() - ox.max())))
        results.append({"n": n, "overlap": round(float(iou), 3), "timing_ok": ok, "box_err": box_err})
        x0, y0, x1, y1 = c.get("_bbox_1080", [0, 0, W, H])
        box = (max(0, x0 - 60), max(0, y0 - 60), min(W, x1 + 60), min(H, y1 + 60))
        rows.append((Image.fromarray(a).crop(box), Image.fromarray(b).crop(box)))
    if rows:
        w = max(r.width for r, _ in rows) * 2 + 10; h = sum(r.height for r, _ in rows) + 10 * len(rows)
        sheet = Image.new("RGB", (w, h), "white"); y = 0
        for r, o in rows:
            sheet.paste(r, (0, y)); sheet.paste(o, (w // 2 + 5, y)); y += r.height + 10
        sheet.save(outdir / "check.jpg", quality=90)
        print(f"  side-by-side (reference left, ours right): {outdir/'check.jpg'}")
    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")               # emoji in output on Windows consoles
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "detect" and len(sys.argv) == 4:
        detect(sys.argv[2], sys.argv[3])
    elif cmd == "fit" and len(sys.argv) == 4:
        fit(sys.argv[2], sys.argv[3])
    elif cmd == "check" and len(sys.argv) == 5:
        check(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
