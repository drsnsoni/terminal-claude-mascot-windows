#!/usr/bin/env python3
"""
clawd_overlay_win.py — a tiny Clawd crab that walks OVER your terminal (Windows).

Windows port of clawd_overlay.swift. A borderless, transparent, always-on-top,
click-through window that draws an animated pixel-art crab. Because it is its
own window, it can overlap the terminal (or any app) without touching the text
underneath — clicks and keystrokes pass straight through.

It knows when Claude is working: hooks installed by install.ps1 write
"working" to ~/.claude/clawd_state on UserPromptSubmit and "idle" on
Stop / SessionEnd. "working" -> Clawd walks / kicks / waves. Otherwise
he stands and blinks.

Pure Python 3 + tkinter (ships with the python.org installer). No compile step.

Run:   pythonw clawd_overlay_win.py            (pythonw = no console window)

Options:
  --corner tr|tl|br|bl   screen corner to live in (default br)
  --margin-x N           horizontal margin from that corner, pt (default 40)
  --margin-y N           vertical margin, pt (default 90 — clears input box)
  --x N --y N            absolute position (bottom-left origin), overrides corner
  --scale N              pixel size in pt (default 4; 3 = smaller, 5 = bigger)
  --lane N               walking lane width in pixels (default 40)
  --always               animate even when Claude is idle
  --action NAME          play only this action instead of cycling: walk,
                         football, flag, look, dumbbell, confetti, ninja,
                         spinner (Claude Code's · ✢ ✳ ✶ ✻ ✽ star)
  --state PATH           state file to watch (default ~/.claude/clawd_state)
  --follow-claude        auto-quit ~15s after the last claude.exe exits
  --follow-name NAME     process name to follow (default claude.exe)
  --track-terminal       stick to the focused terminal window, bottom-right,
                         sitting on top of Claude Code's input box
  --input-offset N       with --track-terminal: gap from the window's bottom edge
                         to the crab's feet, pt (default 100 = top of input box)
  --follow-terminal      auto-quit ~15s after all terminal apps are closed

Stop it:  taskkill /f /fi "WINDOWTITLE eq clawd-overlay"
"""

import argparse
import ctypes
import os
import sys
import time
import tkinter as tk
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clawd_scenes import ACTIONS, SPRITE_H, build_scene  # noqa: E402
from clawd_scenes import COLORS as SCENE_COLORS  # noqa: E402

if sys.platform != "win32":
    sys.exit("clawd_overlay_win.py is Windows-only; on macOS use clawd_overlay.swift")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WINDOW_TITLE = "clawd-overlay"
MUTEX_NAME = "Local\\clawd-overlay"   # single instance; clawd_hook.py checks it too

KEY = "#010203"   # transparency key colour — never used by the sprite
COLORS = {k: "#%02X%02X%02X" % rgb for k, rgb in SCENE_COLORS.items()}

STATE_MAX_AGE = 2 * 60 * 60   # ignore a "working" flag older than 2h

TERMINAL_EXES = {
    "windowsterminal.exe", "openconsole.exe", "conhost.exe",
    "cmd.exe", "powershell.exe", "pwsh.exe",
    "wezterm-gui.exe", "alacritty.exe", "mintty.exe", "hyper.exe",
    "tabby.exe", "warp.exe", "ghostty.exe", "kitty.exe",
}


# ---------------------------------------------------------------- win32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
GA_ROOT = 2
SPI_GETWORKAREA = 0x0030
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DWMWA_EXTENDED_FRAME_BOUNDS = 9

user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsIconic.argtypes = [wintypes.HWND]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def running_exe_names():
    """Lower-cased executable names of every running process (no subprocess)."""
    names = set()
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return names
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return names


def exe_name_of_window(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)


def window_rect(hwnd):
    """Visible bounds (excludes the invisible resize border on Win10/11)."""
    r = wintypes.RECT()
    try:
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) == 0:
            return r
    except OSError:
        pass
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def find_terminal_rect():
    """Bounds of the foreground window if it belongs to a terminal app."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd or user32.IsIconic(hwnd):
        return None
    if exe_name_of_window(hwnd) not in TERMINAL_EXES:
        return None
    r = window_rect(hwnd)
    if r.right - r.left < 200 or r.bottom - r.top < 200:
        return None
    return r


def work_area():
    r = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return r


def enable_dpi_awareness():
    """Returns the scale factor (1.0 at 100%). Per-monitor aware so pixels stay crisp."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    try:
        return user32.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        return 1.0


# ---------------------------------------------------------------- app
class Overlay:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dpi = enable_dpi_awareness()
        self.px = max(1, round(cfg.scale * self.dpi))
        self.w = cfg.lane * self.px
        self.h = SPRITE_H * self.px
        self.frame = 0
        self.misses = 0
        self.visible = True

        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h,
                                bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.cells = {}

        x, y = self.initial_position()
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.root.update_idletasks()
        self.make_click_through()
        if cfg.track_terminal:
            self.hide()

        self.root.after(150, self.tick)
        if cfg.track_terminal:
            self.root.after(300, self.track_terminal)
        if cfg.follow_claude or cfg.follow_terminal:
            self.root.after(5000, self.check_follow)

    def initial_position(self):
        cfg, wa = self.cfg, work_area()
        mx, my = round(cfg.margin_x * self.dpi), round(cfg.margin_y * self.dpi)
        left = cfg.corner in ("tl", "bl")
        top = cfg.corner in ("tl", "tr")
        x = wa.left + mx if left else wa.right - mx - self.w
        y = wa.top + my if top else wa.bottom - my - self.h
        # --x/--y use a bottom-left origin, matching the macOS overlay
        if cfg.x is not None:
            x = wa.left + round(cfg.x * self.dpi)
        if cfg.y is not None:
            y = wa.bottom - round(cfg.y * self.dpi) - self.h
        return x, y

    def make_click_through(self):
        hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        style &= ~WS_EX_APPWINDOW
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

    def show(self):
        if not self.visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.visible = True

    def hide(self):
        if self.visible:
            self.root.withdraw()
            self.visible = False

    def claude_working(self):
        if self.cfg.always:
            return True
        try:
            with open(self.cfg.state, encoding="utf-8") as fh:
                if fh.read().strip() != "working":
                    return False
            return time.time() - os.path.getmtime(self.cfg.state) < STATE_MAX_AGE
        except (OSError, UnicodeDecodeError):
            return False

    def tick(self):
        self.frame += 1
        action = self.cfg.action or ACTIONS[(self.frame // 66) % len(ACTIONS)]  # ~10s each
        scene = build_scene(action, self.frame, self.cfg.lane, not self.claude_working())
        self.draw(scene)
        self.root.after(150, self.tick)

    def draw(self, scene):
        # Reuse one rectangle per cell; only touch cells whose colour changed.
        p = self.px
        for r, row in enumerate(scene.grid):
            for c, ch in enumerate(row):
                colour = COLORS.get(ch)
                item = self.cells.get((r, c))
                if colour is None:
                    if item is not None:
                        self.canvas.itemconfigure(item[0], state="hidden")
                        self.cells[(r, c)] = (item[0], None)
                elif item is None:
                    rid = self.canvas.create_rectangle(
                        c * p, r * p, (c + 1) * p, (r + 1) * p, fill=colour, width=0)
                    self.cells[(r, c)] = (rid, colour)
                elif item[1] != colour:
                    self.canvas.itemconfigure(item[0], fill=colour, state="normal")
                    self.cells[(r, c)] = (item[0], colour)

    def track_terminal(self):
        r = find_terminal_rect()
        if r is None:
            self.hide()
        else:
            margin = round(24 * self.dpi)
            input_margin = round(self.cfg.input_offset * self.dpi)   # top of input box
            x = r.right - self.w - margin
            y = r.bottom - input_margin - self.h
            self.root.geometry(f"+{x}+{y}")
            self.show()
        self.root.after(300, self.track_terminal)

    # Quit after 3 consecutive 5s checks find nothing to follow (~15s grace),
    # so quick restarts and multiple sessions don't kill the crab.
    def check_follow(self):
        names = running_exe_names()
        alive = ((self.cfg.follow_claude and self.cfg.follow_name.lower() in names) or
                 (self.cfg.follow_terminal and bool(names & TERMINAL_EXES - {"conhost.exe"})))
        self.misses = 0 if alive else self.misses + 1
        if self.misses >= 3:
            self.root.destroy()
            return
        self.root.after(5000, self.check_follow)

    def run(self):
        self.root.mainloop()


def parse_args():
    ap = argparse.ArgumentParser(description="Clawd overlay for Windows")
    ap.add_argument("--corner", default="br", choices=["tr", "tl", "br", "bl"])
    ap.add_argument("--margin-x", type=float, default=40)
    ap.add_argument("--margin-y", type=float, default=90)
    ap.add_argument("--x", type=float)
    ap.add_argument("--y", type=float)
    ap.add_argument("--scale", type=float, default=4)
    ap.add_argument("--lane", type=int, default=40)
    ap.add_argument("--always", action="store_true")
    ap.add_argument("--action", choices=ACTIONS)
    ap.add_argument("--state", default="~/.claude/clawd_state")
    ap.add_argument("--follow-claude", action="store_true")
    ap.add_argument("--follow-name", default="claude.exe")
    ap.add_argument("--track-terminal", action="store_true")
    ap.add_argument("--input-offset", type=float, default=100)
    ap.add_argument("--follow-terminal", action="store_true")
    cfg = ap.parse_args()
    cfg.scale = max(1.0, cfg.scale)
    cfg.lane = max(16, cfg.lane)
    cfg.state = os.path.expanduser(cfg.state)
    return cfg


def main():
    cfg = parse_args()
    # Single instance: a second launch (e.g. from another session's hook) exits.
    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
        return
    try:
        Overlay(cfg).run()
    finally:
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
