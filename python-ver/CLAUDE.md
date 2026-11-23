# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This folder (`py/`) holds a standalone pygame platformer demo, `platformer.py`. The repo root is a separate LÖVE 11.5 / Lua game (`main.lua`, `src/`, Tiled maps in `maps/`, see the root `README.md`). The two projects share no code.

## Running

If `python` is not on PATH on this machine and it opens the Microsoft Store, use `py` instead:

```
py platformer.py
```

There is no test suite or linter config. To check mechanics without a window, set `SDL_VIDEODRIVER=dummy` before importing, import `platformer`, build a `Game()`, replace `pygame.key.get_pressed` with a stub that reports chosen keys as held, then call `g.update()` and `g.draw()` in a loop and inspect state (`g.score`, `g.player.big`, `g.level.grid`, enemy `state`). `Player.jump()` only works once a frame has run, because it needs `on_ground`. Set `g.enemies` yourself in tests: the default spawns, like the walker at col 20, will otherwise walk into a test player and kill it.

## Architecture (`platformer.py`, single file)

- **Units are pixels per frame at a fixed 60 FPS.** `T = 48` is the tile size. All tuning values (speeds, gravity, jump, `HITBOX_SCALE`, score tables) are constants at the top of the file.
- **The level** is a 2D char grid built in code by `build_level()` with `put`/`row` calls. Tile codes:
  - `#` ground, `B` brick, `N` multi-coin brick
  - `?` coin block, `M` grow-item block, `U` used block
  - `S` stair block, `p` pipe

  `SOLID` lists the solid codes. Enemy spawns are the separate `ENEMIES` list `(kind, col, row)`, and `PITS` / `CHECK_X` set the gaps and the end point. Out-of-range columns count as solid walls; out-of-range rows count as empty, so pits are open below.
- **Collision** (`Body.move_x` / `move_y`) moves one axis at a time and tests only the leading-edge column or row. This depends on speeds staying below `T` per frame. `move_y` returns the tiles hit, and `Player.update` passes them on only when moving up, as head bumps.
- **Two boxes per enemy:** `rect` (full sprite) handles tile collision; `hitbox` (scaled by `HITBOX_SCALE`, centered) handles every player↔enemy and enemy↔enemy interaction. Stomps count when `player.prev_bottom <= hitbox.top + 12`.
- **Enemy states:** `walk` → `flat` (walker `g`) or `shell` → `slide` (shell enemy `k`), and any of them → `dead` (flipped, falls with no collision). Enemies wake when they come within a screen of the camera. Sliding shells far off screen are removed.
- **`Game` owns all cross-entity rules**: block bumps (`bump_block`, `hit_enemies_above`), scoring and chains (`STOMP_PTS` per player since last landing, `SHELL_PTS` per shell), hurt/death, and item pickup. Entities only move themselves.
- **`Game.reset()` rebuilds everything** (level, entities, score, camera). Death, pits and the R key all just call it, so there is no persistent state to clean up.
- **Draw order matters:** grow items draw before tiles, so they're hidden while rising out of a block. Block bump animation is a per-tile frame countdown in `level.bumps`.

## Design constraints from the user

- The level layout and characters are original, inspired by classic platformer mechanics. Do not turn them into a recreation of a specific existing game's level, characters or art.
- Deliberately excluded: flagpole, stars, enterable pipes, underground areas, fire power, lives, timer.
- The camera scrolls freely both ways. Reaching the checkpoint freezes the game with an overlay.
