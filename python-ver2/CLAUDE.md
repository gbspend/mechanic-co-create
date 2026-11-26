# Rule-driven pygame platformer

Mechanics come from rules (`TRIGGER & TRIGGER -> EFFECT, EFFECT`), not code.
Run `python platformer.py` (pygame 2.6): `-w <name>` loads a world, `-p` opens
world select. In game: P = world select, R = reload, Esc = quit.

## Testing: smoke tests only
- Headless (`SDL_VIDEODRIVER=dummy`): load each touched world, run a few hundred
  frames, and check for crashes and load errors.
- **No gameplay tests** (jump heights, kill counts, simulated play). Tell the user
  what to playtest.

## Files
- **World** = folder with `level.txt` + `RULES.txt`. Base world = this directory;
  others in `worlds/`:
  - `moon`: low gravity, grenades bounce off walls, spikes kill from above only.
  - `runner`: auto-run, breakable `brick` tiles, edge-forgiving spikes, chasers.
  - `bounce`: ride turret orbs.
- `RULES.txt`: the user's files. Preserve their edits and comments. The base
  header is the vocabulary reference; keep it in sync with rules.py.
- `level.txt`: `#` tile, `.` empty, letters place types (`LEGEND X: type`;
  built in: P, G, F). `//` comments. Exactly one player.
- `rules.py`: parser, matcher, vocabulary (`@trigger` / `@effect`).
- `platformer.py`: engine, sprite library, worlds menu.
- `base_plat.py`: frozen original. **Never modify.**

## Engine
- `[section]` = entity type. Options are parsed by `rules.parse_options`:
  - `sprite=` picks from `SPRITES`. Default: the sprite named like the type, else pink.
  - `hitbox=` is any scale > 0, centered and rounded.
  - `tile` (+ `solid=0`) makes a tile type: no rules, no SPAWN, placed by LEGEND.
- `#` is `_tile`. `IS(t, _tile)` matches any tile, and `t(DIE)` removes one.
- `Game.update()` order:
  1. `sense()`: hitbox overlap, or a tile within 1px of the sprite.
  2. Rules run, player first.
  3. Remove the dead (a dead player resets the level).
  4. `move()`: velocity with tile collision, or a STEP glide. `on_ground` comes
     from collision, a 1px probe, or `supported` (set by `STAND_ON`).
  5. Spawns join the world.
- Grid works alongside pixel movement: `_col`/`_row` (row 0 = bottom),
  `STEP(dir, frames)`, `BLOCKED`, `STEPPING`. Helpers: `cell_of`,
  `cell_solid`, `cell_topleft`.
- Feel:
  - `COYOTE_FRAMES` applies to the player; jump rules use `SET(_yvel, n)`.
  - `BUFFER_FRAMES` is the default press lifetime. A press lasts until a firing
    rule uses it.
  - Buffering is per BIND name (`Input.pending`). `BUFFER a b: n` sets a
    lifetime and one shared slot. Feed input via `Input.press()`.
- `load_world()` validates first; on error it keeps the current world.

## Rule semantics
- Entity variables are lowercase names in entity slots. Bind triggers
  (`COLLIDE(e)`, `NEAR(e, d)`, `OWNER(o)`) fill them per candidate, left to right.
  `v(X)` applies X to v. `self` is always bound.
- Vars: `SET`/`ADD`/`SCALE`/`CLAMP` and `CHECK(v op n)`.
  - `_` built-ins live in `BUILTIN_VARS`; add engine state there.
  - Other names live in `ent.vars` and default to 0.
- `AUTO` = every frame, `AUTO(n)` = every n frames.
- Parameter annotations drive load-time checks, with line numbers.
- Rules run top to bottom; a dead entity skips the rest. Y is up-positive.
- To insert rules programmatically, match the whole `\n[section]\n` line.
