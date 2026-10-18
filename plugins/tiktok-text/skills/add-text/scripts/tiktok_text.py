"""Burn in on-screen text that looks like TikTok's own in-app text tool ("Classic" font, no background box).

Verified against real in-app TikToks (measured frame by frame on several creators' videos):
  - Font: TikTok Sans (TikTok's own font, open source, fonts/TikTokSans-VF.ttf) at weight 575, opsz 36, rendered
    from a hinting-free static copy (app_font) with the lowercase "w" widened 8% - the app's build differs there.
    Letter positions match real captions to ~0.2-0.6 px.
  - Each line centred on its own (trailing spaces count, like in the app). Line pitch = 1.188 x size; a blank
    line is exactly one pitch.
  - No shadow (measured ~0-3% on bright skin in 3 videos). Fill colour fully opaque.
  - Size/position are set per video (in the app you pinch to resize): default = a typical lower-third hook.
  - Emoji are Apple's (iPhone) emoji images, downloaded once per emoji from the emoji-data project
    (cdn.jsdelivr.net/gh/iamcal/emoji-data, img-apple-160) into fonts/emoji_apple/. Fitted on a real caption
    ("ts 😭"): emoji box = 1.02 x size, starting 0.015 x size before the pen position,
    bottom 0.14 x size below the baseline, advance 0.975 x size, no outline/shadow around it in any style.
  - Type "…" not "..." to match an iPhone.

Usage:
  python tiktok_text.py IN.mp4 OUT.mp4 captions.json
captions.json = [{"text": "line one\\nline two", "start": 0, "end": 8.067,
                  "style": "classic", "y": 0.646, "size": 70}]   # style/x/y/size optional; seconds (end exclusive)
styles: classic (plain white), outline (white + black outline), yellow (pale), yellow_gold - see STYLES below
  python tiktok_text.py --png "line one\\nline two" out.png      (just the transparent overlay)
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, distance_transform_edt

FONTS = Path(__file__).resolve().parent.parent / "fonts"      # skill folder: scripts/ and fonts/ side by side
FONT = str(FONTS / "TikTokSans-VF.ttf")
# Generated files (font copies, downloaded emoji) go in the plugin's data folder when running from the environment
# setup_check.py made there (it survives plugin updates); otherwise next to the font.
_DATA = Path(sys.prefix).parent
STATE = _DATA if (_DATA / ".add-text-data").exists() else FONTS
CACHE = STATE / "cache"
W, H = 1080, 1920
W_STRETCH = 1.08   # TikTok's in-app lowercase "w" is 8% wider than the open-source font's (fitted on gold, outline and classic captions)
DEFAULTS = dict(size=70.3, weight=575, width=100, opsz=36, line_gap=1.188,   # line pitch = size * line_gap
                x=0.5, y=0.6458, shadow_blur=14.0, shadow_alpha=0.0,      # x/y = text block centre (fraction of frame)
                color="#FFFFFF", outline=0.0, outline_in=0.0, outline_color="#000000")
EMOJI_BOX, EMOJI_DROP, EMOJI_ADV, EMOJI_DX = 1.02, 0.14, 0.975, -0.015    # x font size (see docstring)
EMOJI_DIR = STATE / "emoji_apple"
EMOJI_URL = "https://cdn.jsdelivr.net/gh/iamcal/emoji-data@master/img-apple-160/{}.png"


def _split_emoji(line):
    """[(is_emoji, text), ...] - emoji = grapheme clusters with a pictographic char, flag or keycap."""
    import regex
    out = []
    for cl in regex.findall(r"\X", line):
        emo = bool(regex.search(r"\p{Extended_Pictographic}|\p{Regional_Indicator}|⃣", cl))
        if out and out[-1][0] == emo and not emo:
            out[-1] = (False, out[-1][1] + cl)
        else:
            out.append((emo, cl))
    return out


def _emoji_img(cluster):
    import urllib.request
    cps = [f"{ord(c):x}" for c in cluster]
    names = ["-".join(cps), "-".join(c for c in cps if c != "fe0f"), "-".join(cps[:1] + ["fe0f"] + cps[1:])]
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    for n in dict.fromkeys(names):
        p = EMOJI_DIR / f"{n}.png"
        if not p.exists():
            try:
                p.write_bytes(urllib.request.urlopen(EMOJI_URL.format(n), timeout=20).read())
            except Exception:
                continue
        return Image.open(p).convert("RGBA")
    raise ValueError(f"no Apple emoji image found for {cluster!r} ({names[0]})")


def app_font(weight, width=100, opsz=36):
    """Static instance of TikTok Sans matching the app: hinting removed (the variable font's hinting draws the
    i/j dot 2.4% of size too high; phones don't hint) and lowercase w widened by W_STRETCH. Cached on disk."""
    p = CACHE / f"TikTokSans-app-wght{weight:g}-wdth{width:g}-opsz{opsz:g}-w{W_STRETCH:g}.ttf"
    if p.exists():
        return str(p)
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables import ttProgram
    from fontTools.varLib import instancer
    f = instancer.instantiateVariableFont(TTFont(FONT), {"opsz": opsz, "wdth": width, "wght": weight, "slnt": 0})
    for t in ["fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "gasp"]:
        if t in f:
            del f[t]
    glyf, hmtx = f["glyf"], f["hmtx"]
    for g in glyf.glyphs.values():
        if hasattr(g, "program"):
            g.program = ttProgram.Program(); g.program.fromBytecode(b"")
    w = glyf["w"]
    coords, ends, flags = w.getCoordinates(glyf)
    x0 = min(x for x, _ in coords); x1 = max(x for x, _ in coords)
    w.coordinates = type(coords)([(round(x0 + (x - x0) * W_STRETCH), y) for x, y in coords])
    w.recalcBounds(glyf)
    grow = round((x1 - x0) * (W_STRETCH - 1))
    for name in glyf.keys():                      # w and its accented composites (wacute, wcircumflex, ...)
        g = glyf[name]
        if name == "w" or (g.isComposite() and any(c.glyphName == "w" for c in g.components)):
            adv, lsb = hmtx[name]; hmtx[name] = (adv + grow, lsb)
            if g.isComposite():
                for c in g.components:            # keep accents centred over the wider w
                    if c.glyphName != "w":
                        c.x += grow // 2
                g.recalcBounds(glyf)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.save(str(p))
    return str(p)
# outline / outline_in = how far the stroke reaches outside / inside the letter edge, as a fraction of font size
# Styles measured from real in-app TikToks:
#   classic      white (3 videos)
#   outline      same white letters as classic + crisp solid black stroke 7.5% of the font size, all
#                outside the letter (fills small gaps like the inside of "e"), no shadow. Measured on 3 captions
#                (sizes 74.5, 68, 63.5): stroke = 8.7% of size in all three, and the letters are the same weight as
#                classic (heavier weights fit worse). Confirmed on 4 more videos: 8.0-9.4% of size.
#                Multi-line outline pitch = 1.19 x size (same as classic).
#   yellow       pale yellow #FFF9A3 (mid-point of two videos: (255,251,161) and (255,246,167))
#   yellow_gold  TikTok palette gold #F2CC47 (3 frames agree)
#   lilac        TikTok palette light purple #F9C6FE (90th-percentile letter fill (250,199,255) at 1/5/9/15 s,
#                median 245,196,251)
STYLES = {"classic": {},
          "outline": dict(outline=0.075, outline_in=0.0),
          "lilac": dict(color="#F9C6FE"),
          "yellow": dict(color="#FFF9A3"),
          "yellow_gold": dict(color="#F2CC47")}


def _rgb(h):
    h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def caption_png(text, style="classic", **kw):
    o = {**DEFAULTS, **STYLES[style], **{k: v for k, v in kw.items() if v is not None}}
    f = ImageFont.truetype(app_font(o["weight"], o["width"], o["opsz"]), round(o["size"] * 4))   # 4x supersample
    s = 4
    lines = text.split("\n")
    pitch = o["size"] * o["line_gap"] * s
    asc = f.getbbox("h")[1]                                       # 'h' ascender top offset
    x_h = f.getbbox("h")[3] - asc                                 # ascender-to-baseline height
    block = (len(lines) - 1) * pitch + x_h                        # ascender top of line 1 -> last baseline
    top = o["y"] * H * s - block / 2
    m = Image.new("L", (W * s, H * s), 0)
    d = ImageDraw.Draw(m)
    emojis = []                                                   # (cluster, x, box-bottom y) in 4x coords
    for i, line in enumerate(lines):
        y = top + i * pitch - asc
        parts = _split_emoji(line)
        if not any(e for e, _ in parts):
            bb = d.textbbox((0, 0), line, font=f)
            d.text((o["x"] * W * s - (bb[2] - bb[0]) / 2 - bb[0], y), line, font=f, fill=255)
            continue
        adv = o["size"] * s * EMOJI_ADV
        x = o["x"] * W * s - sum(adv if e else f.getlength(t) for e, t in parts) / 2
        baseline = y + f.getmetrics()[0]
        for e, t in parts:
            if e:
                emojis.append((t, x + EMOJI_DX * o["size"] * s, baseline + EMOJI_DROP * o["size"] * s)); x += adv
            else:
                d.text((x, y), t, font=f, fill=255); x += f.getlength(t)
    if o["outline"]:                                              # crisp stroke on the letter edge, round joins
        mm = np.asarray(m) >= 128
        r_out, r_in = o["outline"] * o["size"] * s, o["outline_in"] * o["size"] * s
        d_out, d_in = distance_transform_edt(~mm), distance_transform_edt(mm)
        ol = np.clip(r_out + 0.5 - d_out, 0, 1)                   # glyph grown by r_out
        if r_in > 0:                                              # fill shrunk by r_in
            m = Image.fromarray((np.where(mm, np.clip(d_in - r_in + 0.5, 0, 1), 0) * 255).astype(np.uint8))
        b = np.asarray(Image.fromarray((ol * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    else:
        b = np.zeros((H, W), np.float32)
    a = np.asarray(m.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    sh = gaussian_filter(np.maximum(a, b), o["shadow_blur"]) * o["shadow_alpha"]
    under = b + sh * (1 - b)                                      # outline over shadow (both dark)
    under_rgb = np.where(b[..., None] > 0, _rgb(o["outline_color"]) * (b / np.maximum(under, 1e-6))[..., None], 0)
    alpha = a + under * (1 - a)                                   # coloured text on top
    rgb = (_rgb(o["color"]) * a[..., None] + under_rgb * (under * (1 - a))[..., None]) / np.maximum(alpha, 1e-6)[..., None]
    out = Image.fromarray(np.dstack([rgb, alpha[..., None] * 255]).clip(0, 255).astype(np.uint8), "RGBA")
    for cl, x, y1 in emojis:                                      # Apple emoji on top, no outline/shadow
        box = o["size"] * EMOJI_BOX
        x0, y0 = x / s, y1 / s - box                              # sub-pixel placement via a padded canvas
        ix, iy = int(np.floor(x0)), int(np.floor(y0))
        n = int(np.ceil(box)) + 2
        big = Image.new("RGBA", (n * 8, n * 8))
        em = _emoji_img(cl).resize((round(box * 8),) * 2, Image.LANCZOS)
        big.alpha_composite(em, (round((x0 - ix) * 8), round((y0 - iy) * 8)))
        out.alpha_composite(big.resize((n, n), Image.LANCZOS), (ix, iy))
    return out


def burn(inp, out, caps):
    tmp = Path(tempfile.mkdtemp())
    args, chain, last = ["ffmpeg", "-v", "error", "-y", "-i", inp], [], "0:v"
    for i, c in enumerate(caps):
        p = tmp / f"cap{i}.png"
        caption_png(c["text"], c.get("style", "classic"),
                    **{k: v for k, v in c.items() if k in DEFAULTS}).save(p)   # any setting can be overridden
        args += ["-i", str(p)]
        chain.append(f"[{last}][{i + 1}:v]overlay=0:0:enable='gte(t,{c['start']})*lt(t,{c['end']})'[v{i}]")
        last = f"v{i}"
    args += ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
             "-c:a", "copy", "-movflags", "+faststart", out]
    subprocess.run(args, check=True)


if __name__ == "__main__":
    if sys.argv[1] == "--png":
        caption_png(sys.argv[2].replace("\\n", "\n")).save(sys.argv[3])
    else:
        burn(sys.argv[1], sys.argv[2], json.load(open(sys.argv[3], encoding="utf-8")))
    print("done")
