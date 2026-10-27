"""Remove captions without touching the rest of the frame: keep the AI (caption-removed) pixels only inside the
caption boxes; everything else stays the original's full-resolution pixels (so the product label is never redrawn).

usage: python S/caption_merge.py original.mp4 ai.mp4 out.mp4 "x,y,w,h,first,last" [...more boxes]
  original.mp4  one shot cut from the reference, captions still on (e.g. 1080x1920, 30 fps)
  ai.mp4        Kling's caption-removed version of it (any fps/size, may be padded to 3 s)
  boxes         x,y,w,h in original pixels, active from frame `first` to `last` (0-based, inclusive).
                TikTok captions sit still on screen, so one box per caption. Pad ~15 px, include emojis, and check
                the boxes by drawing them on a frame first. Keep boxes off the product label where possible.
Each original frame takes the matching AI frame (straight-line time fit) nudged onto the original (ECC affine),
with soft box edges so no seam shows. Note: captions often switch one frame before a cut; replace that frame
with the one before it instead of boxing it."""
import subprocess
import sys
import cv2
import numpy as np

orig_p, ai_p, out_p = sys.argv[1:4]
boxes = [tuple(int(v) for v in b.split(",")) for b in sys.argv[4:]]

co, ca = cv2.VideoCapture(orig_p), cv2.VideoCapture(ai_p)
fo, fa = co.get(cv2.CAP_PROP_FPS), ca.get(cv2.CAP_PROP_FPS)
W, H = int(co.get(cv2.CAP_PROP_FRAME_WIDTH)), int(co.get(cv2.CAP_PROP_FRAME_HEIGHT))
ai = []
while True:
    ok, f = ca.read()
    if not ok:
        break
    ai.append(cv2.resize(f, (W, H), interpolation=cv2.INTER_LANCZOS4))
frames = []
while True:
    ok, f = co.read()
    if not ok:
        break
    frames.append(f)


def small(img):
    return cv2.cvtColor(cv2.resize(img, (90, 160)), cv2.COLOR_BGR2GRAY).astype(np.float32)


def gray_blur(img):
    return cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)


# timing: best-matching AI frame near the expected time (compared outside the boxes), then a straight-line fit
ai_small = [small(a) for a in ai]
keep = np.ones((160, 90), bool)
for x, y, w, h, _, _ in boxes:
    keep[y * 160 // H:(y + h) * 160 // H + 1, x * 90 // W:(x + w) * 90 // W + 1] = False
picked = []
for n, f in enumerate(frames):
    guess = round(n / fo * fa)
    cands = range(max(0, guess - 4), min(len(ai), guess + 5))
    s = small(f)
    picked.append(min(cands, key=lambda k: float(((ai_small[k] - s)[keep] ** 2).mean())))
slope, off = np.polyfit(np.arange(len(frames)), picked, 1)
picked = [int(np.clip(round(slope * n + off), 0, len(ai) - 1)) for n in range(len(frames))]

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                        "-r", str(fo), "-i", "-", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", out_p],
                       stdin=subprocess.PIPE)
ecc_mask = np.full((H, W), 255, np.uint8)  # align on everything outside the caption boxes
for x, y, w, h, _, _ in boxes:
    ecc_mask[max(0, y - 20):y + h + 20, max(0, x - 20):x + w + 20] = 0
warp = np.eye(2, 3, dtype=np.float32)
for n, f in enumerate(frames):
    a = ai[picked[n]]
    try:  # nudge the AI frame onto the original (it can sit a few px off)
        _, warp = cv2.findTransformECC(gray_blur(f), gray_blur(a), warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5), ecc_mask, 5)
    except cv2.error:
        pass  # keep the previous frame's alignment
    a = cv2.warpAffine(a, warp, (W, H), flags=cv2.INTER_LANCZOS4 + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
    m = np.zeros((H, W), np.float32)
    for x, y, w, h, first, last in boxes:
        if first <= n <= last:
            m[y:y + h, x:x + w] = 1
    m = cv2.GaussianBlur(m, (0, 0), 6)[..., None]  # soft edge so the box doesn't show
    out = f * (1 - m) + a * m
    enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close()
enc.wait()
print("frames", len(frames), "AI frames per original frame %.3f (expect ~0.8 for 24 vs 30 fps)" % slope)
