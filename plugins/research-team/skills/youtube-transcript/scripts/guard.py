"""PreToolUse hook for the web-researcher agent: its shell may only run the YouTube transcript tool.

Reads the hook JSON on stdin. Exits 0 to allow the command, or 2 (with a reason on stderr) to block it.
Web pages can contain text aimed at AI agents, so the researcher's shell is locked to this one command shape:
    <youtube-transcript-env python> <this folder>/yt_transcript.py [args...]
with no shell operators, substitutions, redirections or chaining.

Works both as a per-agent hook (local install) and as a plugin-wide hook: calls from any agent other than
web-researcher pass through untouched.
"""
import json
import os
import shlex
import sys

ENV_DIR = os.path.join(os.path.expanduser("~"), ".claude", "youtube-transcript-env")
# Exact paths, not suffixes: an agent could otherwise plant a look-alike script elsewhere.
PYTHON_PATHS = [os.path.join(ENV_DIR, "Scripts", "python.exe"), os.path.join(ENV_DIR, "bin", "python"),
                os.path.join(ENV_DIR, "bin", "python3")]
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt_transcript.py")
# '&' is rejected even inside quotes, so URLs with extra parameters (&t=, &list=) must be trimmed to the video ID.
FORBIDDEN_CHARS = set(";&|<>`$(){}\n\r*!")


def norm(path):
    path = path.strip("\"'")
    # Git Bash style /c/Users/... -> C:/Users/...
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == "/":
        path = path[1] + ":" + path[2:]
    return os.path.normcase(os.path.normpath(os.path.expanduser(path)))


def block(reason):
    print(f"Blocked: {reason} This agent's shell can only run the YouTube transcript tool, in exactly this form:\n"
          f"  \"{PYTHON_PATHS[0] if os.name == 'nt' else PYTHON_PATHS[1]}\" \"{SCRIPT_PATH}\" "
          f"VIDEO_ID [VIDEO_ID ...] [--meta-only] [--lang en] [--no-whisper] [--refresh]\n"
          f"Any other command is not available; don't retry it in another form.", file=sys.stderr)
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        block("could not read the hook input.")
    agent = data.get("agent_type")
    if agent is not None and not str(agent).endswith("web-researcher"):
        sys.exit(0)  # plugin-wide hook: leave other agents and the main session alone
    if data.get("tool_name") not in (None, "Bash"):
        sys.exit(0)
    command = (data.get("tool_input") or {}).get("command") or ""
    # Catch operators and substitutions anywhere, including inside double quotes.
    if any(c in command for c in "`$;|&<>\n\r"):
        block("the command contains shell operators.")
    try:
        # posix=False keeps Windows backslashes; quotes are stripped in norm().
        args = shlex.split(command, posix=False)
    except ValueError:
        block("the command could not be parsed.")
    if len(args) < 3:
        block("expected the environment's python, the script path, and at least one video.")
    if norm(args[0]) not in {norm(p) for p in PYTHON_PATHS}:
        block("the command must start with the youtube-transcript-env python.")
    if norm(args[1]) != norm(SCRIPT_PATH):
        block("the second argument must be the yt_transcript.py script.")
    for arg in args[2:]:
        bad = FORBIDDEN_CHARS & set(arg)
        if bad:
            block(f"argument {arg!r} contains shell characters {''.join(sorted(bad))}; pass the bare 11-character "
                  f"video ID instead.")
    sys.exit(0)


if __name__ == "__main__":
    main()
