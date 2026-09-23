#!/usr/bin/env python3
"""
Claude Code hook helper for the Clawd mascot on Windows.

Windows can't rely on `echo working > ~/.claude/clawd_state` — hooks may run
under Git Bash, cmd or PowerShell, and `~` / `>` behave differently in each.
Calling Python with absolute paths works the same in all of them.

  clawd_hook.py working            write "working" to ~/.claude/clawd_state
  clawd_hook.py idle               write "idle"
  clawd_hook.py start-overlay      launch clawd_overlay_win.py --follow-claude
                                   --track-terminal (crab on top of the input box)
                                   (detached, no console) unless already running
"""

import ctypes
import os
import subprocess
import sys

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
STATE_FILE = os.path.join(CLAUDE_DIR, "clawd_state")
OVERLAY = os.path.join(CLAUDE_DIR, "clawd_overlay_win.py")
MUTEX_NAME = "Local\\clawd-overlay"   # created by the running overlay


def write_state(state):
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        fh.write(state + "\n")


def overlay_running():
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenMutexW.restype = ctypes.c_void_p
    h = kernel32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
    if h:
        kernel32.CloseHandle(ctypes.c_void_p(h))
        return True
    return False


def start_overlay():
    if sys.platform != "win32" or not os.path.exists(OVERLAY) or overlay_running():
        return
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    base = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    # Break away from Claude Code's job object so the crab outlives the hook;
    # fall back if the job doesn't allow breakaway.
    for flags in (base | CREATE_BREAKAWAY_FROM_JOB, base):
        try:
            subprocess.Popen([exe, OVERLAY, "--follow-claude", "--track-terminal"],
                             creationflags=flags, close_fds=True,
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return
        except OSError:
            continue


def main():
    for arg in sys.argv[1:]:
        if arg in ("working", "idle"):
            write_state(arg)
        elif arg == "start-overlay":
            start_overlay()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass   # a hook must never break Claude Code; stay silent
