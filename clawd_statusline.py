#!/usr/bin/env python3
"""
Clawd statusline for Claude Code.

A pixel-art Clawd crab in Anthropic orange that lives in the Claude
Code status line and plays different actions while Claude is working
(walk, football, flag, look, dumbbell, confetti, ninja, and Claude
Code's own · ✢ ✳ ✶ ✻ ✽ spinner — see clawd_scenes.py). While working,
the label also shows the spinner glyph and a verb ("✶ Clauding…").
When Claude is idle, Clawd stands still and blinks.

Pin one action:  python clawd_statusline.py --action spinner

How it animates: Claude Code re-runs the statusline command after each
assistant message and, with "refreshInterval": 1 in the statusLine
config (units: seconds), once a second on a timer. Each run picks a
frame from the wall clock, so successive runs produce successive frames.

How it knows Claude is working: hooks (installed by install.sh) write
"working" to ~/.claude/clawd_state on UserPromptSubmit and "idle" on
Stop / SessionEnd. No state file -> always animate.

Rendering: 8-pixel-tall sprite packed into 4 terminal lines using the
half-block character ▀ (foreground = top pixel, background = bottom
pixel). Terminal width comes from the COLUMNS env var, which Claude
Code sets before running the script (stdout is a pipe here, so
os.get_terminal_size() would lie).

Install (in ~/.claude/settings.json):
  "statusLine": { "type": "command",
                  "command": "python3 ~/.claude/clawd_statusline.py",
                  "padding": 0,
                  "refreshInterval": 1 }
"""

import json
import math
import os
import sys
import time

# Sprite + actions are shared with the overlay (installed next to this file).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clawd_scenes import (ACTIONS, COLORS, SPINNER_VERBS,  # noqa: E402
                          build_scene, spinner_glyph)

ORANGE = COLORS["O"]
LANE = 28           # playfield width in pixels (columns)
FRAME_SECS = 1.0    # matches the 1s refreshInterval
ACTION_SECS = 12    # switch to a new action every N seconds

STATE_FILE = os.path.expanduser("~/.claude/clawd_state")
STATE_MAX_AGE = 2 * 60 * 60   # ignore a "working" flag older than 2h


# ---------------------------------------------------------------- state
def claude_is_working():
    """True when the hook-maintained state file says Claude is generating.

    Missing/unreadable file (hooks not installed) -> True, so the mascot
    still animates like before.
    """
    try:
        with open(STATE_FILE) as fh:
            state = fh.read().strip()
        if state != "working":
            return False
        # Guard against a stale "working" left behind by a crash.
        return (time.time() - os.path.getmtime(STATE_FILE)) < STATE_MAX_AGE
    except (OSError, UnicodeDecodeError):
        return True


# ---------------------------------------------------------------- render
def half_block(top_c, bot_c):
    """Encode two vertically stacked pixels into one character."""
    if top_c is None and bot_c is None:
        return " "
    if top_c is not None and bot_c is not None:
        r, g, b = top_c
        r2, g2, b2 = bot_c
        return f"\x1b[38;2;{r};{g};{b}m\x1b[48;2;{r2};{g2};{b2}m▀\x1b[0m"
    if top_c is not None:
        r, g, b = top_c
        return f"\x1b[38;2;{r};{g};{b}m▀\x1b[0m"
    r, g, b = bot_c
    return f"\x1b[38;2;{r};{g};{b}m▄\x1b[0m"


def render_lines(grid, width=LANE):
    """Pack pixel rows into half-block terminal lines (2 rows per line).

    Renders only the first `width` columns, so a very narrow terminal
    clips the art instead of overflowing/wrapping.
    """
    width = max(0, min(width, LANE))
    lines = []
    for pair in range(0, len(grid), 2):
        top_row = grid[pair] if pair < len(grid) else [None] * LANE
        bot_row = grid[pair + 1] if pair + 1 < len(grid) else [None] * LANE
        line = "".join(half_block(COLORS.get(top_row[c]), COLORS.get(bot_row[c]))
                       for c in range(width))
        lines.append(line)
    return lines


def terminal_columns():
    """Terminal width. Claude Code sets COLUMNS for the statusline command;
    stdout is a pipe, so os.get_terminal_size() is only a dev fallback."""
    try:
        cols = int(os.environ.get("COLUMNS", ""))
        if cols > 0:
            return cols
    except ValueError:
        pass
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


# ---------------------------------------------------------------- main
def main():
    # Windows pipes default to the ANSI codepage (cp1252), which can't
    # encode ▀ / ✻ — force UTF-8 so the art doesn't crash the statusline.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    # Session data from Claude Code (may be absent when testing by hand)
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    m = data.get("model")
    model = (m.get("display_name") if isinstance(m, dict) else None) or "Claude"
    cw = data.get("context_window")
    ctx = cw.get("used_percentage") if isinstance(cw, dict) else None
    ctx_txt = (f" · ctx {int(ctx)}%"
               if isinstance(ctx, (int, float)) and math.isfinite(ctx) else "")

    now = time.time()
    frame = int(now / FRAME_SECS)
    working = claude_is_working()
    pinned = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--action" else None
    action = pinned if pinned in ACTIONS else ACTIONS[int(now // ACTION_SECS) % len(ACTIONS)]
    grid = build_scene(action, frame, LANE, idle=not working).grid

    cols = terminal_columns()

    dim, reset = "\x1b[2m", "\x1b[0m"
    if working:
        # Claude Code's own spinner: ping-ponging glyph + a rotating verb
        verb = SPINNER_VERBS[int(now // ACTION_SECS) % len(SPINNER_VERBS)]
        text_label = f"{spinner_glyph(frame)} {verb}… · {model}{ctx_txt}"
        r, g, b = ORANGE
        style = f"\x1b[38;2;{r};{g};{b}m"
    else:
        text_label = f"✻ {model}{ctx_txt}"
        style = dim
    text_visible_len = len(text_label) + 2  # +2 for leading spaces

    # Three tiers so we never exceed `cols` (an overflow wraps ugly):
    #   wide   -> model/ctx label on the left, art on the right edge
    #   medium -> art only, right-aligned (label wouldn't fit)
    #   narrow -> art only, clipped to the terminal width
    if cols >= text_visible_len + LANE + 2:
        art_w, show_label = LANE, True
    elif cols >= LANE:
        art_w, show_label = LANE, False
    else:
        art_w, show_label = cols, False

    art_lines = render_lines(grid, art_w)

    # Claude Code trims leading whitespace from each statusline line, which
    # would drop the art-only lines to the left edge. Starting every line
    # with an (invisible) reset escape keeps the padding intact.
    try:
        for i, art_line in enumerate(art_lines):
            if show_label and i == 0:
                gap = max(cols - text_visible_len - art_w, 1)
                print(f"{reset}  {style}{text_label}{reset}{' ' * gap}{art_line}")
            else:
                gap = max(cols - art_w, 0)
                print(f"{reset}{' ' * gap}{art_line}")
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
