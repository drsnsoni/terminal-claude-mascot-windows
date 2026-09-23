"""
clawd_scenes.py — the Clawd crab sprite and its animations, shared by
clawd_statusline.py and clawd_overlay_win.py (a straight port of
buildScene in clawd_overlay.swift, plus Claude Code's spinner).

A scene is a grid SPRITE_H rows tall and `lane` pixels wide. Each cell is a
one-letter colour code from COLORS, or "." for transparent. Frontends turn
the grid into half-block terminal characters or window pixels.
"""

import math

# ---------------------------------------------------------------- colors
COLORS = {
    "O": (217, 119, 87),    # Clawd orange #D97757
    "D": (30, 30, 30),      # eyes
    "W": (235, 235, 235),   # ball
    "P": (150, 150, 150),   # pole grey
    "F": (217, 119, 87),    # flag orange
    "Y": (245, 200, 80),
    "B": (100, 180, 240),
    "G": (120, 210, 120),
    "R": (235, 60, 60),
}

SPRITE_W = 12
SPRITE_H = 8

# Claude Code's own "working" spinner: these glyphs ping-pong while it
# thinks, next to a whimsical verb. The "spinner" action draws a pixel-art
# version; the statusline also shows the real glyphs in its label.
SPINNER_GLYPHS = ["·", "✢", "✳", "✶", "✻", "✽"]
SPINNER_SEQ = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1]   # ping-pong through the glyphs
SPINNER_VERBS = ["Clauding", "Thinking", "Pondering", "Noodling", "Percolating",
                 "Cogitating", "Brewing", "Conjuring", "Crafting", "Scheming"]
# Pixel star for each glyph: (orthogonal arm length, diagonal ray distances).
# Diagonal rays start 2px out so small stars read as stars, not blobs.
STAR_ARMS = [(0, ()), (1, ()), (1, (2,)), (2, (2,)), (3, (2,)), (3, (2, 3))]


def spinner_glyph(frame):
    return SPINNER_GLYPHS[SPINNER_SEQ[frame % len(SPINNER_SEQ)]]


# ---------------------------------------------------------------- sprite
# Crab body: 12 wide, 8 tall. Claw pose 0 = claws up, 1 = claws open wider.
# Legs pose 0/1/2 = stand / walk A / walk B. eyes: open, closed, left, right.
def crab_sprite(claw, legs, eyes):
    claw_rows = [
        [".O........O.",
         ".O........O."],
        ["OO........OO",
         ".O........O."],
    ]
    r0, r1 = claw_rows[claw % 2]
    r2 = "..OOOOOOOO.."
    r3 = list("..OOOOOOOO..")
    if eyes == "left":
        r3[3] = "D"; r3[7] = "D"
    elif eyes == "right":
        r3[4] = "D"; r3[8] = "D"
    elif eyes != "closed":
        r3[4] = "D"; r3[7] = "D"
    r4 = ".OOOOOOOOOO."
    r5 = "..OOOOOOOO.."
    leg_rows = [
        ["..O.O..O.O..", "..O.O..O.O.."],
        [".O..O..O..O.", ".O..O..O..O."],
        ["..O..OO..O..", "..O..OO..O.."],
    ]
    l0, l1 = leg_rows[legs % 3]
    return [r0, r1, r2, "".join(r3), r4, r5, l0, l1]


# ---------------------------------------------------------------- scene
class Scene:
    def __init__(self, lane):
        self.lane = lane
        self.grid = [["."] * lane for _ in range(SPRITE_H)]

    def place(self, sprite, x, dy=0):
        """Draw sprite at column x, shifted up by dy rows (for hops)."""
        for r, row in enumerate(sprite):
            tr = r - dy
            if not 0 <= tr < SPRITE_H:
                continue
            for c, ch in enumerate(row):
                col = x + c
                if ch != "." and 0 <= col < self.lane:
                    self.grid[tr][col] = ch

    def put(self, r, c, ch):
        if 0 <= r < SPRITE_H and 0 <= c < self.lane:
            self.grid[r][c] = ch


ACTIONS = ["walk", "football", "flag", "look", "dumbbell", "confetti", "ninja",
           "spinner"]


def build_scene(action, frame, lane, idle):
    s = Scene(lane)
    center = (lane - SPRITE_W) // 2
    if idle:
        eyes = "closed" if frame % 23 == 7 else "open"
        s.place(crab_sprite((frame // 8) % 2, 0, eyes), center)
        return s

    if action == "walk":
        span = max(lane - SPRITE_W, 1)
        pos = frame % (2 * span)
        x = pos if pos < span else 2 * span - pos
        eyes = "right" if pos < span else "left"
        hop = 1 if frame % 4 in (1, 2) else 0
        s.place(crab_sprite(frame % 2, frame, eyes), x, hop)

    elif action == "football":
        cycle = frame % 16
        if cycle < 4:                         # run up
            s.place(crab_sprite(0, cycle, "right"), cycle)
            s.put(SPRITE_H - 1, cycle + SPRITE_W + 2, "W")
        elif cycle == 4:                      # kick
            s.place(crab_sprite(1, 2, "right"), 4)
            s.put(SPRITE_H - 1, 4 + SPRITE_W + 2, "W")
        elif cycle <= 7:                      # ball rising
            s.place(crab_sprite(0, 0, "right"), 4)
            bx = 4 + SPRITE_W + 2 + (cycle - 4) * 2
            by = SPRITE_H - 1 - (cycle - 4)
            s.put(max(by, 0), bx, "W")
        else:                                 # ball rolling away
            s.place(crab_sprite(0, 0, "right"), 4)
            s.put(SPRITE_H - 1, 4 + SPRITE_W + 2 + (cycle - 4), "W")

    elif action == "flag":
        x = 4
        s.place(crab_sprite(0, 0, "open"), x)
        pole = x + SPRITE_W + 1
        for r in range(SPRITE_H):
            s.put(r, pole, "P")
        wave = frame % 2
        for r in range(3):                    # checkered flag
            for c in range(1, 4):
                s.put(r, pole + c, "W" if (r + c + wave) % 2 == 0 else "D")

    elif action == "look":
        seq = ["open", "open", "right", "right", "open", "left", "left", "open"]
        eyes = "closed" if frame % 11 == 7 else seq[frame % len(seq)]
        s.place(crab_sprite((frame // 4) % 2, 0, eyes), center)

    elif action == "dumbbell":
        cycle = frame % 16
        x = center
        if cycle < 4:
            db_y, claw = 4, 1
        elif cycle < 6:
            db_y, claw = 2, 0
        elif cycle < 10:                      # high + struggle shake
            db_y, claw = 0, 0
            x += -1 if cycle % 2 == 0 else 1
        elif cycle < 12:
            db_y, claw = 2, 0
        else:
            db_y, claw = 4, 1
        s.place(crab_sprite(claw, 0, "open"), x)
        for dx in (x - 2, x + SPRITE_W):
            s.put(db_y, dx, "W"); s.put(db_y, dx + 1, "P"); s.put(db_y, dx + 2, "W")
            s.put(db_y + 1, dx, "W"); s.put(db_y + 1, dx + 2, "W")

    elif action == "confetti":
        jump = [0, 0, 1, 1, 2, 2, 1, 1][(frame // 2) % 8]
        s.place(crab_sprite(frame % 2, frame, "open"), center, jump)
        colors = ["Y", "B", "G", "W"]
        for p in range(5):
            start_x = p * (lane // 5)
            offset = int(math.sin((frame + p) * 0.7) * 2.0)
            px = (start_x + offset + lane) % lane
            py = (p * 5 + frame) % SPRITE_H
            if s.grid[py][px] == ".":
                s.grid[py][px] = colors[(p + frame) % len(colors)]

    elif action == "ninja":
        cycle = frame % 16
        x = center
        if cycle <= 3:
            jump, kick, bow = 0, False, False
        elif cycle <= 5:
            jump, kick, bow = 1, False, False
        elif cycle <= 10:
            jump, kick, bow = 2, True, False
        elif cycle <= 12:
            jump, kick, bow = 1, False, False
        else:
            jump, kick, bow = 0, False, True
        claw = 1 if kick else 0
        legs = 2 if kick else (0 if bow else 1)
        shift = jump - (1 if bow else 0)
        s.place(crab_sprite(claw, legs, "right"), x, shift)
        head = 2 - shift                      # red headband
        if 0 <= head < SPRITE_H:
            for c in range(2, 10):
                s.put(head, x + c, "R")
            if frame % 2 == 0:
                s.put(head, x - 1, "R"); s.put(head + 1, x - 2, "R")
            else:
                s.put(head + 1, x - 1, "R"); s.put(head, x - 2, "R")
        if kick:                              # flying kick extension
            kr = 6 - shift
            s.put(kr, x + SPRITE_W, "O"); s.put(kr, x + SPRITE_W + 1, "O")
        if cycle >= 6:                        # shuriken
            shx = x + SPRITE_W + 2 + (cycle - 6) * 3
            shy = 3 - shift
            if cycle % 2 == 0:
                s.put(shy, shx, "D"); s.put(shy + 1, shx + 1, "D")
            else:
                s.put(shy, shx + 1, "D"); s.put(shy + 1, shx, "D")

    elif action == "spinner":
        # Claude Code's spinner as a pixel star that grows · ✢ ✳ ✶ ✻ ✽ and
        # shrinks back, while the crab watches it and taps its claws.
        x = max(center - 4, 0)
        eyes = "closed" if frame % 13 == 9 else "right"
        s.place(crab_sprite(frame % 2, 0, eyes), x)
        ortho, diag = STAR_ARMS[SPINNER_SEQ[frame % len(SPINNER_SEQ)]]
        cx, cy = x + SPRITE_W + 5, 3
        s.put(cy, cx, "O")
        for d in range(1, ortho + 1):
            s.put(cy - d, cx, "O"); s.put(cy + d, cx, "O")
            s.put(cy, cx - d, "O"); s.put(cy, cx + d, "O")
        for d in diag:
            s.put(cy - d, cx - d, "O"); s.put(cy - d, cx + d, "O")
            s.put(cy + d, cx - d, "O"); s.put(cy + d, cx + d, "O")
    return s
