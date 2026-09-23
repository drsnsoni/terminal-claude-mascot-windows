#!/usr/bin/env bash
# Installs the Clawd mascot for Claude Code:
#   1. Statusline mascot  — animates in the Claude Code status line
#   2. Overlay mascot     — floats OVER the terminal (macOS, optional)
#   3. Hooks              — tell the mascot when Claude is working vs idle
#
# Safe to re-run. settings.json is backed up first, and hooks are
# APPENDED — your existing hooks are never touched.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"

mkdir -p "$CLAUDE_DIR/bin"

# 1. ---- statusline script -------------------------------------------------
cp "$SCRIPT_DIR/clawd_scenes.py" "$CLAUDE_DIR/clawd_scenes.py"   # sprite + actions
cp "$SCRIPT_DIR/clawd_statusline.py" "$CLAUDE_DIR/clawd_statusline.py"
chmod +x "$CLAUDE_DIR/clawd_statusline.py"
echo "Installed statusline script -> ~/.claude/clawd_statusline.py"

# 2. ---- overlay app (macOS + swiftc only) ---------------------------------
OVERLAY_OK=0
if [[ "$(uname)" == "Darwin" ]] && command -v swiftc >/dev/null 2>&1; then
  echo "Compiling overlay app (one-time, a few seconds)..."
  if swiftc -O -swift-version 5 \
       -o "$CLAUDE_DIR/bin/clawd-overlay" \
       "$SCRIPT_DIR/clawd_overlay.swift"; then
    OVERLAY_OK=1
    echo "Installed overlay app -> ~/.claude/bin/clawd-overlay"
  else
    echo "WARNING: overlay compile failed — statusline mascot still works."
  fi
else
  echo "NOTE: overlay app skipped (needs macOS + Xcode command line tools:"
  echo "      xcode-select --install). Statusline mascot still works."
fi

# 3. ---- settings.json: statusLine + state hooks ---------------------------
if [ -f "$SETTINGS" ]; then
  cp "$SETTINGS" "$SETTINGS.backup.$(date +%Y%m%d%H%M%S)"
  echo "Backed up existing settings.json"
fi

python3 - "$SETTINGS" <<'EOF'
import json, os, sys

path = sys.argv[1]
data = {}
if os.path.exists(path):
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            sys.exit("ERROR: settings.json is not valid JSON — fix it first, "
                     "nothing was changed.")
    if not isinstance(data, dict):
        sys.exit("ERROR: settings.json is not a JSON object — fix it first, "
                 "nothing was changed.")

# --- statusLine: refreshInterval keeps the animation ticking (1 fps) ---
# NOTE: refreshInterval is in SECONDS (Claude Code re-runs every N seconds).
existing = data.get("statusLine")
if existing and "clawd_statusline" not in json.dumps(existing):
    print(f"NOTE: replacing your existing statusLine config: {existing}")
data["statusLine"] = {
    "type": "command",
    "command": "python3 ~/.claude/clawd_statusline.py",
    "padding": 0,
    "refreshInterval": 1,
}

# --- hooks: state file for working/idle + auto start/stop the overlay ---
# Appended alongside any hooks you already have; skipped if present.
# SessionStart launches the overlay (if built and not already running) in
# --follow-claude mode, so it quits by itself ~15s after the last claude
# process exits. All output is redirected: SessionStart stdout would
# otherwise leak into Claude's context.
OVERLAY_LAUNCH = (
    "[ -x ~/.claude/bin/clawd-overlay ] && "
    "! pgrep -f clawd-overlay >/dev/null 2>&1 && "
    "(nohup ~/.claude/bin/clawd-overlay --follow-claude >/dev/null 2>&1 &) "
    "|| true"
)
CLAWD_HOOKS = {
    "SessionStart":     [OVERLAY_LAUNCH,
                         "echo working > ~/.claude/clawd_state"],
    "UserPromptSubmit": ["echo working > ~/.claude/clawd_state"],
    "Stop":             ["echo idle > ~/.claude/clawd_state"],
    "SessionEnd":       ["echo idle > ~/.claude/clawd_state"],
}
hooks = data.setdefault("hooks", {})
for event, commands in CLAWD_HOOKS.items():
    entries = hooks.setdefault(event, [])
    if "clawd" in json.dumps(entries):
        continue  # already installed
    entries.append({
        "hooks": [{"type": "command", "command": cmd, "timeout": 5}
                  for cmd in commands]
    })
    print(f"Added clawd hook(s) to {event}")

with open(path, "w") as f:
    json.dump(data, f, indent=2)
print("settings.json updated:", path)
EOF

# 4. ---- done ---------------------------------------------------------------
echo
echo "Done! Restart Claude Code (and accept the trust prompt if asked)."
echo "Clawd animates in the status line while Claude works, idles otherwise."
if [ "$OVERLAY_OK" = 1 ]; then
  echo
  echo "To ALSO get the crab floating over your terminal (like the video):"
  echo "  ~/.claude/bin/clawd-overlay &                # bottom-right corner"
  echo "  ~/.claude/bin/clawd-overlay --corner tr &    # top-right"
  echo "  ~/.claude/bin/clawd-overlay --scale 2 &      # smaller"
  echo "  ~/.claude/bin/clawd-overlay --always &       # dance even when idle"
  echo "Stop it with:  pkill -f clawd-overlay"
  echo "Survive terminal close:  nohup ~/.claude/bin/clawd-overlay >/dev/null 2>&1 & disown"
fi
echo
echo "Preview a statusline frame right now:"
echo '  echo "{}" | COLUMNS=$(tput cols) python3 ~/.claude/clawd_statusline.py'
