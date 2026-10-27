"""Put the real product label back onto an AI-edited shot (close-ups only), and re-time the AI shot to the original.

usage: python S/label_patch.py original.mp4 ai.mp4 out.mp4 x,y,w,h [--no-patch]
  original.mp4  the shot with the real label, captions already removed (caption_merge.py output).
                It sets the output's frame count and fps (e.g. 30 fps).
  ai.mp4        the AI-edited version of the same shot (e.g. Kling's background swap: 24 fps, padded to 3 s).
  x,y,w,h       rectangle around the printed words on the original's first frame (1080x1920 coords). Keep it inside
                the product with a margin of plain packaging around the text, off fingers. Draw it on a frame first.
  --no-patch    don't patch, just output the AI frames re-timed to the original (use for far shots: small print is
                unreadable there anyway, and patching a small product makes it look like a pasted cutout).
                The rectangle is still used to match timing, so put it on the product.

How: picks the AI frame that matches each original frame (straight-line fit, no stutter), aligns the original onto
it (ECC affine on the product area, smoothed over time), then lays the original's label into a soft-edged window,
re-lit with the AI frame's broad brightness so it blends. Runs on CPU in about a minute per shot."""
import subprocess
import sys
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

orig_p, ai_p, out_p, rect = sys.argv[1:5]
patch_label = "--no-patch" not in sys.argv[5:]
rx, ry, rw, rh = (int(v) for v in rect.split(","))


def read(p, size=None):
    c, out = cv2.VideoCapture(p), []
    while True:
        ok, f = c.read()
        if not ok:
            return out, c.get(cv2.CAP_PROP_FPS)
        out.append(cv2.resize(f, size, interpolation=cv2.INTER_LANCZOS4) if size else f)


def g(img, s=2.0):
    return cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), s).astype(np.float32)


orig, fo = read(orig_p)
H, W = orig[0].shape[:2]
ai, fa = read(ai_p, (W, H))

# 1. timing: best-matching AI frame near the expected time, then a straight-line fit (no stutter)
roi = np.zeros((H, W), np.uint8)
roi[max(0, ry - 150):ry + rh + 150, max(0, rx - 150):rx + rw + 150] = 1  # product area only (backgrounds differ)
small = lambda img: cv2.resize(g(img, 3) * roi, (90, 160))
ai_s = [small(a) for a in ai]
picks = []
for n, f in enumerate(orig):
    guess = round(n / fo * fa)
    cands = range(max(0, guess - 4), min(len(ai), guess + 5))
    s = small(f)
    picks.append(min(cands, key=lambda k: float(((ai_s[k] - s) ** 2).mean())))
slope, off = np.polyfit(np.arange(len(orig)), picks, 1)
picks = [int(np.clip(round(slope * n + off), 0, len(ai) - 1)) for n in range(len(orig))]

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                        "-r", str(fo), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", out_p],
                       stdin=subprocess.PIPE)

if not patch_label:
    for n in range(len(orig)):
        enc.stdin.write(ai[picks[n]].tobytes())
else:
    # 2. alignment: warp that maps the original onto the AI frame, tracked on the product
    ecc_mask = (roi * 255).astype(np.uint8)
    warps, warp = [], np.eye(2, 3, dtype=np.float32)
    for n, f in enumerate(orig):
        try:
            _, warp = cv2.findTransformECC(g(ai[picks[n]]), g(f), warp, cv2.MOTION_AFFINE,
                                           (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-6), ecc_mask, 5)
        except cv2.error:
            pass  # keep the previous frame's alignment
        warps.append(warp.copy())
    warps = gaussian_filter1d(np.array(warps), 1.5, axis=0)  # smooth over time: no jitter

    # 3. composite: the original's letters, the AI frame's lighting, soft-edged window
    win = np.zeros((H, W), np.float32)
    win[ry:ry + rh, rx:rx + rw] = 1
    win = cv2.GaussianBlur(win, (0, 0), 14)
    blur = lambda x: cv2.GaussianBlur(x, (0, 0), 40)  # wide, so the letters themselves don't make halos
    for n, f in enumerate(orig):
        a = ai[picks[n]].astype(np.float32)
        M = warps[n].astype(np.float32)
        o = cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LANCZOS4 + cv2.WARP_INVERSE_MAP,
                           borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        m = cv2.warpAffine(win, M, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)[..., None]
        patch = o * np.clip((blur(a) + 1) / (blur(o) + 1), 0.7, 1.4)
        out = a * (1 - m) + patch * m
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close()
enc.wait()
print("frames", len(orig), "AI frames per original frame %.3f (expect ~0.8 for 24 vs 30 fps)" % slope)
