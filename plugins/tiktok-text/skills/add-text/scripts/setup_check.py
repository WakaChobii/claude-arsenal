"""First-run setup + check for the add-text skill.

  python setup_check.py DATA_DIR
      Creates a private Python environment in DATA_DIR/venv (once), installs requirements.txt into it, checks
      ffmpeg/ffprobe and builds the font copy. Safe to re-run: takes a couple of seconds once everything is there.
      Last line is either
        READY PY=<path to the environment's python>     -> run every add-text script with that python
        NOT READY: <what is missing and how to fix it>

add_text.py also imports check() from here to re-check before each job.
"""
import importlib, os, platform, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REQS = SKILL / "requirements.txt"
PACKAGES = {"numpy": "numpy", "PIL": "Pillow", "scipy": "scipy", "fontTools": "fonttools", "regex": "regex",
            "cv2": "opencv-python"}                      # import name -> pip name
MARKER = ".add-text-data"                                # tells tiktok_text.py where to keep its font cache/emoji


def _ffmpeg_fix():
    s = platform.system()
    if s == "Windows":
        return "winget install Gyan.FFmpeg   (then open a new terminal / restart Claude Code so PATH updates)"
    if s == "Darwin":
        return ("brew install ffmpeg   (no Homebrew? install it first from https://brew.sh)" if shutil.which("brew")
                else "install Homebrew from https://brew.sh, then: brew install ffmpeg")
    return "sudo apt install ffmpeg   (or your distro's package manager)"


def check(quiet=False):
    """True if everything needed is importable in THIS python and ffmpeg/ffprobe are on PATH."""
    problems = []
    missing = []
    for mod, pip in PACKAGES.items():
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(pip)
    if missing:
        problems.append(f"missing Python packages in {sys.executable}: {', '.join(missing)} - run setup_check.py first")
    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            problems.append(f"{exe} not found on PATH. Fix: {_ffmpeg_fix()}")
    if not (SKILL / "fonts" / "TikTokSans-VF.ttf").exists():
        problems.append("font missing: fonts/TikTokSans-VF.ttf (reinstall the plugin)")
    if problems:
        print("NOT READY: " + " | ".join(problems))
    elif not quiet:
        print("add-text: ready")
    return not problems


def _venv_python(venv):
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup(data_dir):
    if sys.version_info < (3, 9):
        print(f"NOT READY: Python {sys.version.split()[0]} is too old. Install Python 3.9+ from https://python.org")
        return 1
    data = Path(data_dir).expanduser()
    data.mkdir(parents=True, exist_ok=True)
    (data / MARKER).write_text("add-text plugin data (python env, font cache, emoji)\n", encoding="utf-8")
    venv = data / "venv"
    py = _venv_python(venv)
    if not py.exists():
        print(f"creating Python environment in {venv} (one time) ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "venv", str(venv)])
        if r.returncode or not py.exists():
            print("NOT READY: could not create a Python environment (on Debian/Ubuntu: sudo apt install python3-venv)")
            return 1
    probe = "import " + ", ".join(PACKAGES)
    if subprocess.run([str(py), "-c", probe], capture_output=True).returncode:
        print("installing Python packages (one time, about 1-2 minutes) ...", flush=True)
        subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"])
        r = subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(REQS)])
        if r.returncode or subprocess.run([str(py), "-c", probe], capture_output=True).returncode:
            print(f"NOT READY: package install failed. Try: \"{py}\" -m pip install -r \"{REQS}\"")
            return 1
    # font copy (hinting removed, w widened) - built once per weight, takes a few seconds the first time
    r = subprocess.run([str(py), "-c", f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); "
                        "import tiktok_text; tiktok_text.app_font(575)"], capture_output=True, text=True)
    if r.returncode:
        print(f"NOT READY: could not build the font copy: {r.stderr.strip()[-300:]}")
        return 1
    missing = [e for e in ("ffmpeg", "ffprobe") if not shutil.which(e)]
    if missing:
        print(f"NOT READY: {' and '.join(missing)} not found on PATH. Fix: {_ffmpeg_fix()}")
        return 1
    print(f"READY PY={py.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 2:
        sys.exit(setup(sys.argv[1]))
    sys.exit(0 if check() else 1)
