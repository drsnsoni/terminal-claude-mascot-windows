#!/usr/bin/env python3
"""
Installs the Clawd mascot for Claude Code on Windows:
  1. Statusline mascot  — animates in the Claude Code status line
  2. Overlay mascot     — floats OVER the terminal (tkinter, no compile step)
  3. Hooks              — tell the mascot when Claude is working vs idle

Safe to re-run. settings.json is backed up first, and hooks are
APPENDED — your existing hooks are never touched.

Usage:  python install_windows.py [--no-overlay]
"""

import ctypes
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
FILES = ["clawd_scenes.py", "clawd_statusline.py", "clawd_hook.py", "clawd_overlay_win.py"]


def shell_path(path):
    """A path usable unquoted in Git Bash, cmd AND PowerShell.

    Claude Code may run hook/statusline commands under any of those shells,
    and each quotes differently (PowerShell treats a leading "quoted path"
    as a string, not a command). So: forward slashes, and if there are
    spaces (e.g. C:\\Program Files\\Python314), use the 8.3 short name.
    """
    if " " in path:
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf)) and " " not in buf.value:
            path = buf.value
        else:
            sys.exit(f"ERROR: path has spaces and no 8.3 short name: {path}\n"
                     "Install Python to a path without spaces and re-run.")
    return path.replace("\\", "/")


def main():
    if sys.platform != "win32":
        sys.exit("This installer is for Windows. On macOS/Linux run ./install.sh")
    want_overlay = "--no-overlay" not in sys.argv

    os.makedirs(CLAUDE_DIR, exist_ok=True)

    # 1. ---- copy scripts ---------------------------------------------------
    for name in FILES:
        shutil.copy2(os.path.join(HERE, name), os.path.join(CLAUDE_DIR, name))
        print(f"Installed {name} -> ~/.claude/{name}")

    overlay_ok = False
    if want_overlay:
        try:
            import tkinter  # noqa: F401  (python.org installer ships it)
            overlay_ok = True
        except ImportError:
            print("NOTE: tkinter missing — overlay skipped. Re-run the Python "
                  "installer with 'tcl/tk and IDLE' ticked. Statusline still works.")

    py = shell_path(sys.executable)
    hook = shell_path(os.path.join(CLAUDE_DIR, "clawd_hook.py"))
    statusline = shell_path(os.path.join(CLAUDE_DIR, "clawd_statusline.py"))

    # 2. ---- settings.json: statusLine + state hooks --------------------------
    data = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8-sig") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                sys.exit("ERROR: settings.json is not valid JSON — fix it first, "
                         "nothing was changed.")
        if not isinstance(data, dict):
            sys.exit("ERROR: settings.json is not a JSON object — fix it first, "
                     "nothing was changed.")
        backup = f"{SETTINGS}.backup.{time.strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(SETTINGS, backup)
        print("Backed up existing settings.json ->", backup)

    # refreshInterval is in SECONDS — keeps the animation ticking at ~1 fps.
    existing = data.get("statusLine")
    if existing and "clawd_statusline" not in json.dumps(existing):
        print(f"NOTE: replacing your existing statusLine config: {existing}")
    data["statusLine"] = {
        "type": "command",
        "command": f"{py} {statusline}",
        "padding": 0,
        "refreshInterval": 1,
    }

    session_start = [f"{py} {hook} working"]
    if overlay_ok:
        # --follow-claude: the overlay quits ~15s after the last claude.exe exits
        session_start = [f"{py} {hook} start-overlay working"]
    clawd_hooks = {
        "SessionStart":     session_start,
        "UserPromptSubmit": [f"{py} {hook} working"],
        "Stop":             [f"{py} {hook} idle"],
        "SessionEnd":       [f"{py} {hook} idle"],
    }
    hooks = data.setdefault("hooks", {})
    for event, commands in clawd_hooks.items():
        entries = hooks.setdefault(event, [])
        if "clawd" in json.dumps(entries):
            continue  # already installed
        entries.append({
            "hooks": [{"type": "command", "command": cmd, "timeout": 5}
                      for cmd in commands]
        })
        print(f"Added clawd hook(s) to {event}")

    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("settings.json updated:", SETTINGS)

    # 3. ---- done -------------------------------------------------------------
    print()
    print("Done! Restart Claude Code (and accept the trust prompt if asked).")
    print("Clawd animates in the status line while Claude works, idles otherwise.")
    if overlay_ok:
        pyw = shell_path(os.path.join(os.path.dirname(sys.executable), "pythonw.exe"))
        ov = shell_path(os.path.join(CLAUDE_DIR, "clawd_overlay_win.py"))
        print()
        print("The floating crab starts automatically with each Claude Code session.")
        print("Run it by hand with other options:")
        print(f"  {pyw} {ov}                     # bottom-right corner")
        print(f"  {pyw} {ov} --track-terminal    # stick to the focused terminal")
        print(f"  {pyw} {ov} --corner tr --scale 2 --always")
        print('Stop it with:  taskkill /f /fi "WINDOWTITLE eq clawd-overlay"')


if __name__ == "__main__":
    main()
