#!/usr/bin/env sh
# Plugin-wide PreToolUse hook for Bash. Only the web-researcher agent is restricted (guard.py does the checks);
# every other agent and the main session pass straight through. Fails closed for web-researcher if no Python works.
input=$(cat)
case "$input" in
  *'"agent_type"'*'web-researcher"'*) ;;
  *) exit 0 ;;
esac
dir=$(dirname "$0")
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    printf '%s' "$input" | "$py" "$dir/guard.py"
    rc=$?
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then exit "$rc"; fi
  fi
done
echo "Blocked: no working Python was found to check this command." >&2
exit 2
