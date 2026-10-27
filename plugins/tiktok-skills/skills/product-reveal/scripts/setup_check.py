"""First-run setup + check for the product-reveal skill.

  python setup_check.py [DATA_DIR]
      Creates a private Python environment in DATA_DIR/venv (once; default DATA_DIR = ~/.claude/tiktok-skills,
      shared with the add-text skill), installs requirements.txt into it and checks ffmpeg/ffprobe.
      Safe to re-run: takes a couple of seconds once everything is there. Last line is either
        READY PY=<path to the environment's python>     -> run every product-reveal script with that python
        NOT READY: <what is missing and how to fix it>
"""
import os, platform, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REQS = SKILL / "requirements.txt"
PACKAGES = ("numpy", "cv2", "scipy")                     # import names (pip: numpy, opencv-python, scipy)
DEFAULT_DATA = Path.home() / ".claude" / "tiktok-skills"


def _ffmpeg_fix():
    s = platform.system()
    if s == "Windows":
        return "winget install Gyan.FFmpeg   (then open a new terminal / restart Claude Code so PATH updates)"
    if s == "Darwin":
        return ("brew install ffmpeg   (no Homebrew? install it first from https://brew.sh)" if shutil.which("brew")
                else "install Homebrew from https://brew.sh, then: brew install ffmpeg")
    return "sudo apt install ffmpeg   (or your distro's package manager)"


def _venv_python(venv):
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup(data_dir=None):
    if sys.version_info < (3, 9):
        print(f"NOT READY: Python {sys.version.split()[0]} is too old. Install Python 3.9+ from https://python.org")
        return 1
    # an empty or unexpanded argument (e.g. "${VAR}" that the shell left alone) means: use the default
    data = Path(data_dir).expanduser() if data_dir and "$" not in data_dir else DEFAULT_DATA
    data.mkdir(parents=True, exist_ok=True)
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
        print("installing Python packages (one time, about 1 minute) ...", flush=True)
        subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"])
        r = subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(REQS)])
        if r.returncode or subprocess.run([str(py), "-c", probe], capture_output=True).returncode:
            print(f"NOT READY: package install failed. Try: \"{py}\" -m pip install -r \"{REQS}\"")
            return 1
    missing = [e for e in ("ffmpeg", "ffprobe") if not shutil.which(e)]
    if missing:
        print(f"NOT READY: {' and '.join(missing)} not found on PATH. Fix: {_ffmpeg_fix()}")
        return 1
    print(f"READY PY={py.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(setup(sys.argv[1] if len(sys.argv) > 1 else None))
