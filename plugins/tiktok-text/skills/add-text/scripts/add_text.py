"""One-command front end for the add-text skill (wraps caption_match.py + tiktok_text.py).

Copy a reference TikTok's captions onto our video:
  python add_text.py start  REF.mp4 WORKDIR
      setup check + detect: writes WORKDIR/captions.json (text "??") and WORKDIR/caption_<n>.png crops.
      -> read the crops, fill in each "text" (and retime start/end if our cuts differ), then:
  python add_text.py finish REF.mp4 OUR.mp4 WORKDIR [OUT.mp4] [--no-fit]
      fit (size/position/spaces) -> trim captions to our video's length -> burn -> check, with a PASS/REVIEW summary.
      OUT defaults to OUR's name with "(no text)" -> "(WITH TEXT)". --no-fit keeps the size/y/x already in the json.

New captions, no reference:
  python add_text.py new OUR.mp4 captions.json [OUT.mp4]
      burn + preview.jpg (one frame per caption) next to captions.json.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_check

GOOD_1080, GOOD_LOWRES = 0.75, 0.68          # letter-overlap bars (low-res references score ~0.70 even when right)


def _out_name(ours, out):
    if out:
        return Path(out)
    p = Path(ours)
    name = p.name.replace("(no text)", "(WITH TEXT)") if "(no text)" in p.name else f"{p.stem} (WITH TEXT){p.suffix}"
    return p.with_name(name)


def _trim_to(caps, dur):
    """End captions at our video's end (and drop ones that start after it)."""
    kept = []
    for n, c in enumerate(caps, 1):
        if c["start"] >= dur:
            print(f"  {n}: starts at {c['start']:.2f}s, after our video ends ({dur:.2f}s) - dropped")
            continue
        if c["end"] > dur:
            print(f"  {n}: end {c['end']:.3f}s -> {dur:.3f}s (our video's length)")
            c["end"] = round(dur, 4)
        kept.append(c)
    return kept


def start(ref, workdir):
    if not setup_check.check(quiet=True):
        sys.exit(1)
    import caption_match as cm
    cm.detect(ref, workdir)
    print(f"\nNext: read each {Path(workdir) / 'caption_<n>.png'} and fill in \"text\" in captions.json, then run finish.")


def finish(ref, ours, workdir, out=None, do_fit=True):
    if not setup_check.check(quiet=True):
        sys.exit(1)
    import caption_match as cm, tiktok_text as tt
    cj = Path(workdir) / "captions.json"
    caps = json.loads(cj.read_text(encoding="utf-8"))
    todo = [n for n, c in enumerate(caps, 1) if "??" in c["text"]]
    if todo:
        sys.exit(f"captions {todo} still have text \"??\" - fill them in from the caption_<n>.png crops first")
    if do_fit:
        print("FIT")
        cm.fit(ref, cj)
        caps = json.loads(cj.read_text(encoding="utf-8"))
    fps_o, n_o = cm.probe(ours)
    print("TIMING")
    caps = _trim_to(caps, n_o / fps_o)
    cj.write_text(json.dumps(caps, indent=1, ensure_ascii=False), encoding="utf-8")
    out = _out_name(ours, out)
    print(f"BURN -> {out}")
    tt.burn(str(ours), str(out), caps)
    print("CHECK")
    res = cm.check(ref, str(out), cj)
    _, n_out = cm.probe(str(out))
    ref_w = int(cm.subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                   "-of", "csv=p=0", ref], capture_output=True, text=True).stdout.strip() or 1080)
    bar = GOOD_1080 if ref_w >= 1000 else GOOD_LOWRES
    problems = []
    if n_out != n_o:
        problems.append(f"frame count changed: {n_o} in, {n_out} out")
    for r in res:
        if not r["timing_ok"]:
            problems.append(f"caption {r['n']}: on/off frames don't match")
        if r["overlap"] < bar:
            if r["box_err"] is not None and r["box_err"] <= 4:
                problems.append(f"caption {r['n']}: overlap {r['overlap']:.2f} < {bar}, but the text block's edges match the "
                                f"reference within {r['box_err']} px, so size/position are right; likely letter-level "
                                "compression in the reference. Confirm the wording by eye in check.jpg")
            else:
                problems.append(f"caption {r['n']}: overlap {r['overlap']:.2f} < {bar}, edges off by {r['box_err']} px "
                                "(typo, missed line break, wrong style?)")
    if len(res) < len(caps):
        problems.append(f"only {len(res)} of {len(caps)} captions could be checked")
    print(f"\nSUMMARY  {out.name}: {n_out} frames ({n_o} in), reference {ref_w}px wide, overlap bar {bar}")
    print("  PASS" if not problems else "  REVIEW:\n" + "\n".join("    - " + p for p in problems))
    print(f"  Look at {Path(workdir) / 'check.jpg'} (reference left, ours right) and show the user before calling it done.")


def new(ours, cap_json, out=None):
    if not setup_check.check(quiet=True):
        sys.exit(1)
    import caption_match as cm, tiktok_text as tt
    from PIL import Image
    cj = Path(cap_json)
    caps = json.loads(cj.read_text(encoding="utf-8"))
    fps, n = cm.probe(ours)
    caps = _trim_to(caps, n / fps)
    out = _out_name(ours, out)
    print(f"BURN -> {out}")
    tt.burn(str(ours), str(out), caps)
    thumbs = [Image.fromarray(cm.frame_at(str(out), (c["start"] + c["end"]) / 2)).resize((360, 640), Image.LANCZOS)
              for c in caps]
    if thumbs:
        sheet = Image.new("RGB", (370 * len(thumbs) - 10, 640), "white")
        for i, t in enumerate(thumbs):
            sheet.paste(t, (i * 370, 0))
        sheet.save(cj.parent / "preview.jpg", quality=90)
    _, n_out = cm.probe(str(out))
    print(f"\nSUMMARY  {out.name}: {n_out} frames ({n} in){'' if n_out == n else '  <-- FRAME COUNT CHANGED'}")
    for i, c in enumerate(caps, 1):
        print(f"  {i}. {c['start']:.3f}-{c['end']:.3f}s  {c.get('style', 'classic')}  {c['text']!r}")
    print(f"  Look at {cj.parent / 'preview.jpg'} and show the user.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    cmd = a[0] if a else ""
    if cmd == "start" and len(a) == 3:
        start(a[1], a[2])
    elif cmd == "finish" and len(a) in (4, 5):
        finish(a[1], a[2], a[3], a[4] if len(a) == 5 else None, do_fit="--no-fit" not in sys.argv)
    elif cmd == "new" and len(a) in (3, 4):
        new(a[1], a[2], a[3] if len(a) == 4 else None)
    else:
        print(__doc__)
