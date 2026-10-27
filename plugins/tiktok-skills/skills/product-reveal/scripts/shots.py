"""Frame-accurate shot tools for the product-reveal skill (ffmpeg + OpenCV, CPU only).

  detect  VIDEO [OUT_DIR]           fps/frames, every cut (frame numbers), fades/black frames, and a numbered
                                    contact sheet (OUT_DIR/_sheet.png, one tile every 5 frames) to look at
  cut     VIDEO START END OUT       frames START..END-1 (0-based, END exclusive), full res, no audio, near-lossless
  pad     IN OUT [FRAMES]           play forward-backward-forward until FRAMES long (default 90 = 3 s at 30 fps);
                                    Kling edits need >= 3 s. Only the first len(IN) frames are kept later.
  holdlast IN OUT                   replace the last frame with the one before (captions often switch 1 frame early)
  frame   VIDEO N OUT.png           save frame N at full size
  boxes   FRAME.png OUT.png BOX...  draw "x,y,w,h" boxes (caption boxes / label rectangle) to check them
  assemble OUT SHOT... [--hold K --fade N]
                                    concat shots; optional fade up from black: K held copies of the first frame
                                    are added in front and the first N frames fade in from black
  check   OUT REF START END [DIR]   compare OUT with REF frames START..END-1: frame counts, cuts, and a 2 fps
                                    reference-over-output overview (DIR/_compare.png)
"""
import os
import re
import subprocess
import sys
import cv2
import numpy as np


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def info(path):
    c = cv2.VideoCapture(path)
    return c.get(cv2.CAP_PROP_FPS), int(c.get(cv2.CAP_PROP_FRAME_COUNT))


def cuts(path, start=0, end=None, thr=0.2):
    vf = f"trim=start_frame={start}" + (f":end_frame={end}" if end else "") + \
         f",setpts=PTS-STARTPTS,select='gt(scene,{thr})',showinfo"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", vf, "-f", "null", "-"],
                       capture_output=True, text=True)
    fps, _ = info(path)
    return [round(float(t) * fps) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def read_frames(path):
    c, out = cv2.VideoCapture(path), []
    while True:
        ok, f = c.read()
        if not ok:
            return out
        out.append(f)


def detect(video, out_dir="."):
    fps, n = info(video)
    print(f"{video}\n  fps {fps:.3f}, {n} frames, {n / fps:.2f} s")
    print("  cuts at frames:", cuts(video))
    c = cv2.VideoCapture(video)
    lum, tiles, i = [], [], 0
    while True:
        ok, f = c.read()
        if not ok:
            break
        lum.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean())
        if i % 5 == 0:
            t = cv2.resize(f, (135, 240))
            cv2.putText(t, str(i), (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(t, str(i), (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            tiles.append(t)
        i += 1
    black = [k for k, v in enumerate(lum) if v < 8]
    if black:
        print("  black frames:", black)
    d = np.diff(lum)
    fades, k = [], 0
    while k < len(d):  # runs of >= 4 frames all getting brighter (or darker) by > 2 each = a fade
        j = k
        while j < len(d) and abs(d[j]) > 2 and np.sign(d[j]) == np.sign(d[k]):
            j += 1
        if j - k >= 4:
            fades.append(f"{k}-{j} ({'in/brighter' if d[k] > 0 else 'out/darker'})")
        k = max(j, k + 1)
    if fades:
        print("  fades (frame ranges):", ", ".join(fades))
    cols = 12
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)]
    path = os.path.join(out_dir, "_sheet.png")
    cv2.imwrite(path, np.vstack(rows))
    print("  contact sheet (frame number on each tile, every 5 frames):", path)


def cut(video, start, end, out):
    ff("-i", video, "-an", "-vf", f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS",
       "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", out)
    print(out, info(out)[1], "frames")


def pad(src, out, frames=90):
    fr = read_frames(src)
    seq, fwd = list(fr), False
    while len(seq) < frames:
        seq += (fr if fwd else fr[::-1])[1:]
        fwd = not fwd
    write(seq[:max(frames, len(fr))], out, info(src)[0])
    print(out, max(frames, len(fr)), "frames (first", len(fr), "are the real shot)")


def write(frames, out, fps, crf=10):
    h, w = frames[0].shape[:2]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", out],
                         stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()


def holdlast(src, out):
    fr = read_frames(src)
    fr[-1] = fr[-2]
    write(fr, out, info(src)[0])
    print(out, len(fr), "frames")


def frame(video, n, out):
    c = cv2.VideoCapture(video)
    c.set(cv2.CAP_PROP_POS_FRAMES, int(n))
    ok, f = c.read()
    cv2.imwrite(out, f)


def boxes(img_path, out, *bs):
    im = cv2.imread(img_path)
    for b in bs:
        x, y, w, h = (int(v) for v in b.split(",")[:4])
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 255), 5)
    cv2.imwrite(out, cv2.resize(im, (im.shape[1] * 500 // im.shape[0], 500)) if im.shape[0] > 1200 else im)


def assemble(out, shots, hold=0, fade=0):
    parts = []
    for k, s in enumerate(shots):
        fr = read_frames(s)
        if k == 0 and hold:
            fr = [fr[0]] * hold + fr
        if k == 0 and fade:
            for i in range(min(fade, len(fr))):
                fr[i] = (fr[i].astype(np.float32) * (i + 1) / (fade + 1)).astype(np.uint8)
        parts += fr
    write(parts, out, info(shots[0])[0], crf=14)
    print(out, len(parts), "frames; cuts at", cuts(out))


def check(out, ref, start, end, out_dir="."):
    start, end = int(start), int(end)
    print("output frames:", info(out)[1], "| reference section frames:", end - start)
    print("output cuts:   ", cuts(out))
    print("reference cuts:", cuts(ref, start, end))
    a, b = os.path.join(out_dir, "_row_ref.png"), os.path.join(out_dir, "_row_out.png")
    n = (end - start + 14) // 15
    ff("-i", ref, "-vf", f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS,fps=2,scale=150:-1,"
       f"tile={n}x1", "-frames:v", "1", a)
    ff("-i", out, "-vf", f"fps=2,scale=150:-1,tile={n}x1", "-frames:v", "1", b)
    ff("-i", a, "-i", b, "-filter_complex", "vstack", os.path.join(out_dir, "_compare.png"))
    os.remove(a)
    os.remove(b)
    print("overview (top = reference):", os.path.join(out_dir, "_compare.png"))


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "detect":
        detect(*args)
    elif cmd == "cut":
        cut(args[0], int(args[1]), int(args[2]), args[3])
    elif cmd == "pad":
        pad(args[0], args[1], int(args[2]) if len(args) > 2 else 90)
    elif cmd == "holdlast":
        holdlast(*args)
    elif cmd == "frame":
        frame(*args)
    elif cmd == "boxes":
        boxes(*args)
    elif cmd == "assemble":
        hold = int(args[args.index("--hold") + 1]) if "--hold" in args else 0
        fade = int(args[args.index("--fade") + 1]) if "--fade" in args else 0
        shots = [a for i, a in enumerate(args[1:], 1) if not a.startswith("--")
                 and args[i - 1] not in ("--hold", "--fade")]
        assemble(args[0], shots, hold, fade)
    elif cmd == "check":
        check(*args)
    else:
        print(__doc__)
