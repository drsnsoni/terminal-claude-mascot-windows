# clawd-mascot

Two ways to put a tiny animated **Clawd** in your Claude Code CLI, both driven by the same "is Claude working?" signal:

| Mode | Where it lives | Overlaps the terminal? |
|---|---|---|
| **Statusline mascot** | Claude Code status line (bottom bar) | No — it has its own row, never touches your text |
| **Overlay crab** (macOS + Windows) | A tiny transparent window floating **on top of** the terminal | Yes — exactly like the video: it sits over the UI, and clicks/typing pass straight through it |

Both animate **while Claude is generating** (walk ⚽ football 🚩 flag 👀 look-around 🏋 dumbbell 🎉 confetti 🥷 ninja ✻ Claude spinner) and stand still, blinking, when Claude is idle.

The **spinner** action is Claude Code's own working animation: a pixel star that grows `· ✢ ✳ ✶ ✻ ✽` and shrinks back. The Python statusline and the Windows overlay have it. The macOS Swift overlay doesn't yet.

## Why two modes (the honest answer)

A terminal is a character grid — a program can't draw *on top of* Claude Code's chat text without overwriting it. So true overlap (the black-mark spot in your screenshot) is done with a separate **click-through overlay window**, not terminal output. Inside the terminal itself, the supported place for custom visuals is the **statusline**. This repo gives you both.

## Install

### Windows

Needs Python 3 from [python.org](https://www.python.org/downloads/) (includes tkinter; the Microsoft Store `python3` stub won't do). In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1              # or: python install_windows.py
powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoOverlay   # statusline only
```

Then restart Claude Code. The installer copies `clawd_statusline.py`, `clawd_hook.py` and `clawd_overlay_win.py` to `%USERPROFILE%\.claude\`, backs up `settings.json`, and adds the statusline plus hooks. The hooks call `python clawd_hook.py working|idle` rather than `echo > file`, so they behave the same whether Claude Code runs them in Git Bash, cmd or PowerShell. Paths containing spaces are written in their 8.3 short form (`C:/PROGRA~1/...`) so they work unquoted in all three shells.

The overlay crab starts on its own with each Claude Code session (`--follow-claude`) and quits about 15s after the last `claude.exe` exits. To run it by hand:

```powershell
pythonw $HOME\.claude\clawd_overlay_win.py                    # bottom-right of the work area
pythonw $HOME\.claude\clawd_overlay_win.py --track-terminal   # stick to the focused terminal window
pythonw $HOME\.claude\clawd_overlay_win.py --corner tr --scale 2 --always
taskkill /f /fi "WINDOWTITLE eq clawd-overlay"                  # stop it
```

It takes the same options as the macOS overlay (below). `--scale` is in points (default 4) and follows your display scaling. Terminals `--track-terminal` recognizes: Windows Terminal, conhost (cmd/PowerShell), WezTerm, Alacritty, mintty (Git Bash), Hyper, Tabby, Warp, Ghostty. Only one overlay runs at a time; a second launch exits immediately.

Uninstall: remove the `statusLine` block and the `clawd_hook.py` hook entries from `settings.json` (or restore the backup), then delete `clawd_*.py` and `clawd_state` from `%USERPROFILE%\.claude\`.

### macOS / Linux

```bash
chmod +x install.sh
./install.sh
```

Then restart Claude Code. The installer:

- copies `clawd_statusline.py` to `~/.claude/` and configures `statusLine` (with `refreshInterval: 1` — units are seconds — so the animation ticks ~1 fps even mid-generation)
- compiles `clawd_overlay.swift` to `~/.claude/bin/clawd-overlay` (macOS + Xcode command line tools; skipped gracefully otherwise)
- **appends** three tiny hooks (`UserPromptSubmit` → `working`, `Stop`/`SessionEnd` → `idle`) that write `~/.claude/clawd_state` — your existing hooks are untouched, and `settings.json` is backed up first

## The overlay crab (the video thing)

```bash
~/.claude/bin/clawd-overlay &                 # bottom-right of screen
```

Options:

```
--corner tr|tl|br|bl   which screen corner (default br)
--margin-x N           horizontal margin in pt (default 40)
--margin-y N           vertical margin in pt (default 90, clears the input box)
--x N --y N            exact position (origin = bottom-left of screen)
--scale N              pixel size: 2 = small, 3 = default, 4 = chunky
--lane N               how wide an area he walks, in pixels (default 40)
--always               animate even when Claude is idle
--action NAME          Windows overlay only: play one action (walk, football, flag, look,
                       dumbbell, confetti, ninja, spinner) instead of cycling
--state PATH           state file to watch (default ~/.claude/clawd_state)
```

- Always on top of the terminal, **below** the menu bar, visible in every Space and over fullscreen apps.
- **Click-through**: it never steals a click or a keystroke.
- No permissions, no Dock icon, ~0% CPU.
- Stop: `pkill -f clawd-overlay`. Survive terminal close: `nohup ~/.claude/bin/clawd-overlay >/dev/null 2>&1 & disown`

## The statusline mascot

Shows `✻ <model> · ctx N%` on the left and the 4-row crab animation against the right edge. While Claude is working, the label turns orange and shows Claude Code's spinner glyph and a verb, e.g. `✶ Clauding… · Opus 5.5 · ctx 18%`:

```
  ✶ Clauding… · Opus 5.5 · ctx 18%                    [tiny animated Clawd]
```

Preview without Claude Code:

```bash
echo '{"model":{"display_name":"Opus 5.5"},"context_window":{"used_percentage":18}}' \
  | COLUMNS=$(tput cols) python3 clawd_statusline.py
```

(`COLUMNS` matters: Claude Code sets it for the statusline command; without it the art can't right-align.)

## How working/idle detection works

Hooks write a one-word state file:

- `UserPromptSubmit` → `working` (you sent a prompt, Claude is on it)
- `Stop` / `SessionEnd` → `idle`

Both mascots read `~/.claude/clawd_state`. No file → statusline animates always, overlay idles (use `--always`). A `working` older than 2 h is treated as stale (crash guard). Note: with multiple Claude Code sessions running at once, the last event wins.

## Customize

- The sprite, colors and every action are in `clawd_scenes.py`, which the statusline and the Windows overlay share. Add a branch to `build_scene` and a name to `ACTIONS`. The macOS overlay has its own copy in Swift (`buildScene`).
- `SPINNER_VERBS` in `clawd_scenes.py` holds the verbs shown in the statusline label.
- `ACTION_SECS` in `clawd_statusline.py` sets how often the action changes.
- Pin one action in the statusline: add `--action spinner` to the end of its `command` in `settings.json`.

## Uninstall

- Remove the `statusLine` block and the three `clawd_state` hook entries from `~/.claude/settings.json` (or restore the backup the installer made)
- `rm ~/.claude/clawd_statusline.py ~/.claude/bin/clawd-overlay ~/.claude/clawd_state`
- `pkill -f clawd-overlay`

## Notes

- Statusline requires the workspace **trust prompt** to be accepted (same rule as hooks).
- If the status line goes blank, run the preview command above to surface errors.
- Truecolor ANSI is used for the statusline art — every modern terminal (Terminal.app, iTerm2, Ghostty, kitty, WezTerm) supports it.
- Linux: the statusline mascot works anywhere Python 3 does. The overlay is available on macOS and Windows only.
# terminal-claude-mascot
