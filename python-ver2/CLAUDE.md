# Rule-driven pygame platformer

An experiment in building game mechanics from a grammar of rules
(`TRIGGER & TRIGGER -> EFFECT, EFFECT`) instead of hardcoded behavior.
Run: `python platformer.py` (pygame 2.6). `-w <name>` loads a world directly
and `-p` starts at the world select list. In game: **P** opens world select,
**R** reloads the current world's files and restarts, **Esc** quits.

## Files
- A **world** is a folder holding `level.txt` and `RULES.txt`, which are always
  loaded together. The base world (named `base`) is this directory, and the
  others are `worlds/<name>/` (`moon`, `runner`, `bounce`).
- `RULES.txt`: all entity behavior. These are the user's experiment files, so
  preserve their edits and comments (including commented-out rules). The base
  `RULES.txt` header is the full vocabulary reference.
- `level.txt`: the map. `#` is a tile, `.` is empty, letters spawn entities.
  `//` starts a comment, since `#` is a tile. `LEGEND X: type [as look]` adds
  letters to the built-in P/G/F, and exactly one player start is required.
- `rules.py`: the parser, the matcher, and the trigger/effect vocabulary. To
  add vocabulary, write a function with `@trigger("NAME")` or `@effect("NAME")`.
- `platformer.py`: the engine (level, sprites, physics, contact sensing, spawning).
- `base_plat.py`: frozen copy of the original hardcoded game. **Never modify.**

## Engine model
- Everything that acts is an `Entity`. Its `kind` is its entity type and the
  `[section]` of `RULES.txt` it runs. Art lives in `build_kinds()` (player,
  walker, flyer, bullet, turret, orb). A `LEGEND ... as look` line reuses art
  for a new type, and any other type gets a pink placeholder. Any `[type]` can
  be `SPAWN`ed.
- Tiles are `Tile` objects of engine type `_tile` (`ENGINE_TYPES`). They don't
  run rules, but they show up in `COLLIDE`, and `t(DIE)` removes one.
- Each frame, `Game.update()` does this:
  1. `sense()`: entities touch when their hitboxes overlap, and touch a tile
     when it's within 1px of their sprite rect.
  2. Every entity runs its rules, player first, then the rest in list order.
  3. Remove the dead. If the player is dead, the level resets.
  4. `move()` applies velocity with tile collision. `on_ground` comes from
     the collision plus a 1px probe below, or from `supported`, which
     `STAND_ON` sets to make another entity act as floor.
  5. Spawned entities join the world.
- Feel settings live in the engine, not in the rules (`platformer.py` constants):
  - `COYOTE_FRAMES`: the player keeps `on_ground` for a few frames after walking
    off a ledge, and moving up ends it. Jump rules should use `SET_YVEL`, so a
    coyote jump is full strength.
  - `BUFFER_FRAMES`: a key press keeps `BUTTON_PRESS` true until a rule that
    tests it fires (`Input.use`), and it's used up at the end of that frame.
    Feed input through `Input.press()`, not by touching `pressed` directly.
- The camera follows the player on both axes, so levels can be any size.
- `Game.load_world()` validates the level and the rules before switching. On an
  error it keeps the current world and shows the message.
- The engine has no gameplay logic left: gravity, jumping, stomping, bullets
  and death are all rules.

## Rule semantics (rules.py)
- Lowercase names are variables. A "bind" trigger fills one in, once per
  candidate (`COLLIDE(e)`, `NEAR(e, d)`, `OWNER(o)`), and effects run once
  per match. `v(X)` checks or applies X on entity v, and `self` is always
  bound. Variables must be bound left to right.
- Function parameter annotations (`"bind"`, `"ref"`, `"type"`, `"spawn"`,
  `"button"`, `"dir"`) drive the checks at load time. Arity is checked too,
  and errors report the line number.
- Rules run top to bottom. Once an entity dies, the rest of its rules are skipped.
- Y velocity in rules is **up-positive**. `rules.py` converts it to pygame's
  y-down, where `ent.vy` lives.
- `RULES.txt` header comments are the user-facing vocabulary reference. Keep
  them in sync when you add or remove triggers or effects.

## Conventions
- Test headlessly with `SDL_VIDEODRIVER=dummy`. To simulate input, set
  `game.input.pressed` and monkeypatch `pygame.key.get_pressed`.
- When inserting rules into `RULES.txt` programmatically, match the whole
  `\n[section]\n` line: comments mention section names like `[walker]`.
