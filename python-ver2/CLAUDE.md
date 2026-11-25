# Rule-driven pygame platformer

An experiment in building game mechanics from a grammar of rules
(`TRIGGER & TRIGGER -> EFFECT, EFFECT`) instead of hardcoded behavior.
Run: `python platformer.py` (pygame 2.6). In game: **R** reloads `RULES.txt`
and restarts the level, **Esc** quits.

## Files
- `RULES.txt`: all entity behavior. It's the user's experiment file, so
  preserve their edits and comments (including commented-out rules).
- `rules.py`: the parser, the matcher, and the trigger/effect vocabulary. To
  add vocabulary, write a function with `@trigger("NAME")` or `@effect("NAME")`.
- `platformer.py`: the engine (level, sprites, physics, contact sensing, spawning).
- `base_plat.py`: frozen copy of the original hardcoded game. **Never modify.**

## Engine model
- Everything that acts is an `Entity`. Its `kind` is its entity type and the
  `[section]` of `RULES.txt` it runs. Types with art are in `build_kinds()`,
  and level letters map to types in `LEGEND`. A `[type]` that exists only in
  `RULES.txt` gets a pink placeholder sprite and can be `SPAWN`ed.
- Tiles are `Tile` objects of engine type `_tile` (`ENGINE_TYPES`). They don't
  run rules, but they show up in `COLLIDE`, and `t(DIE)` removes one.
- Each frame, `Game.update()` does this:
  1. `sense()`: entities touch when their hitboxes overlap, and touch a tile
     when it's within 1px of their sprite rect.
  2. Every entity runs its rules, player first, then the rest in list order.
  3. Remove the dead. If the player is dead, the level resets.
  4. `move()` applies velocity with tile collision.
  5. Spawned entities join the world.
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
