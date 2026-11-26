"""Rule-driven 2D platformer.

A world is a folder holding a level.txt (the map) and a RULES.txt (all entity
behavior; see rules.py for the grammar). The base world is this directory;
more live in worlds/<name>/. The engine only moves things, collides them with
tiles, and senses contacts.

    python platformer.py              play the base world
    python platformer.py -w <name>    play worlds/<name>
    python platformer.py -p           start at the world select list

Keys: R reloads the world's files and restarts, P opens world select, Esc quits.
Movement keys come from the world's RULES.txt (BIND lines).
"""
import argparse
import sys
from pathlib import Path

import pygame

import rules

# ---------------------------------------------------------------- settings
TILE = 32
SCREEN_W, SCREEN_H = 800, 480
FPS = 60

BASE_DIR = Path(__file__).resolve().parent
WORLDS_DIR = BASE_DIR / "worlds"
BASE_WORLD = "base"           # menu / -w name for the level.txt + RULES.txt in BASE_DIR

ENGINE_TYPES = ("_tile",)  # entity types the engine provides, usable in IS(e, type)

HITBOX_SCALE = 0.7        # enemy hitbox size relative to its sprite, centered

# Feel, independent of RULES.txt
COYOTE_FRAMES = 6         # player still counts as ON_GROUND this many frames after walking off a ledge
BUFFER_FRAMES = 6         # a button press stays live this many frames until a rule uses it
                          # (default; BUFFER lines in RULES.txt set it per button)

# Level letters every world gets; a level.txt can add more with LEGEND lines.
# '#' is always a plain tile (type _tile, sprite "ground").
DEFAULT_LEGEND = {"P": "player", "G": "walker", "F": "flyer"}

SKY = (120, 180, 235)
GRASS = (70, 170, 60)
DIRT = (140, 95, 55)
DIRT_DARK = (110, 72, 40)


# ---------------------------------------------------------------- helpers
def make_tile():
    surf = pygame.Surface((TILE, TILE))
    surf.fill(DIRT)
    for x, y in ((6, 12), (20, 20), (12, 26), (25, 9)):
        pygame.draw.rect(surf, DIRT_DARK, (x, y, 4, 3))
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    return surf


def make_grass_tile():
    surf = make_tile()
    pygame.draw.rect(surf, GRASS, (0, 0, TILE, 8))
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    return surf


def make_brick_tile():
    surf = pygame.Surface((TILE, TILE))
    surf.fill((170, 75, 50))
    mortar = (215, 195, 170)
    for y in (0, 8, 16, 24):
        pygame.draw.line(surf, mortar, (0, y), (TILE, y), 2)
        off = 0 if (y // 8) % 2 == 0 else TILE // 2
        for x in (off, off + TILE // 2):
            pygame.draw.line(surf, mortar, (x % TILE, y), (x % TILE, y + 8), 2)
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    return surf


def make_water_tile():
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    surf.fill((40, 110, 220, 140))
    pygame.draw.line(surf, (200, 230, 255, 200), (4, 6), (14, 6), 2)
    pygame.draw.line(surf, (200, 230, 255, 200), (18, 16), (28, 16), 2)
    return surf


def make_spikes_sprite():
    """Fills most of the tile, so it reads right as a solid tile type too."""
    surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    pygame.draw.rect(surf, (70, 70, 80), (0, TILE - 6, TILE, 6))               # base plate
    for i in range(4):
        x = i * 8
        tip = [(x, TILE - 6), (x + 4, 4), (x + 8, TILE - 6)]
        pygame.draw.polygon(surf, (200, 200, 210), tip)
        pygame.draw.polygon(surf, (60, 60, 70), tip, 1)
    return surf


def make_player_sprite(facing):
    w, h = 24, 30
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (220, 50, 50), (2, 8, 20, 16), border_radius=4)   # body
    pygame.draw.rect(surf, (255, 210, 170), (4, 0, 16, 11), border_radius=4)  # head
    pygame.draw.rect(surf, (40, 40, 140), (3, 24, 7, 6))                      # legs
    pygame.draw.rect(surf, (40, 40, 140), (14, 24, 7, 6))
    eye_x = 15 if facing > 0 else 7
    pygame.draw.rect(surf, (0, 0, 0), (eye_x, 3, 3, 4))
    gun_x = 18 if facing > 0 else 0
    pygame.draw.rect(surf, (60, 60, 60), (gun_x, 14, 6, 4))                   # blaster
    return surf


def make_walker_sprite(frame):
    w, h = 32, 32
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (150, 90, 40), (1, 2, 30, 24))                  # body
    foot = 3 if frame else 0
    pygame.draw.ellipse(surf, (60, 35, 15), (2 + foot, 24, 11, 8))
    pygame.draw.ellipse(surf, (60, 35, 15), (19 - foot, 24, 11, 8))
    for ex in (9, 19):
        pygame.draw.ellipse(surf, (255, 255, 255), (ex, 9, 6, 8))
        pygame.draw.rect(surf, (0, 0, 0), (ex + 2, 11, 2, 4))
    pygame.draw.line(surf, (0, 0, 0), (8, 7), (14, 9), 2)                     # angry brows
    pygame.draw.line(surf, (0, 0, 0), (24, 7), (18, 9), 2)
    return surf


def make_flyer_sprite(frame):
    w, h = 32, 28
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    wing_y = 2 if frame else 10
    pygame.draw.polygon(surf, (200, 200, 255), [(9, 14), (0, wing_y), (3, 18)])
    pygame.draw.polygon(surf, (200, 200, 255), [(23, 14), (32, wing_y), (29, 18)])
    pygame.draw.ellipse(surf, (130, 50, 170), (6, 6, 20, 20))                 # body
    pygame.draw.circle(surf, (255, 230, 60), (16, 14), 5)                     # eye
    pygame.draw.circle(surf, (0, 0, 0), (16, 14), 2)
    return surf


def make_bullet_sprite():
    surf = pygame.Surface((10, 4), pygame.SRCALPHA)
    surf.fill((255, 240, 80))
    return surf


def make_placeholder_sprite():
    """For entity types that exist only in RULES.txt and have no art yet."""
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    surf.fill((230, 60, 200))
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
    return surf


def make_turret_sprite(facing):
    surf = pygame.Surface((28, 28), pygame.SRCALPHA)
    pygame.draw.rect(surf, (90, 95, 110), (2, 10, 24, 18), border_radius=3)   # base
    pygame.draw.circle(surf, (120, 125, 140), (14, 12), 9)                    # dome
    barrel_x = 14 if facing > 0 else 0
    pygame.draw.rect(surf, (40, 40, 50), (barrel_x, 9, 14, 6))                # barrel
    pygame.draw.circle(surf, (255, 80, 60), (14, 12), 3)                      # eye
    return surf


def make_orb_sprite(frame):
    surf = pygame.Surface((18, 18), pygame.SRCALPHA)
    pygame.draw.circle(surf, (120, 230, 255), (9, 9), 9 if frame else 8)
    pygame.draw.circle(surf, (230, 250, 255), (7, 6), 3)
    return surf


# ---------------------------------------------------------------- entities
class Entity:
    """Anything with rules: the player and every enemy.

    Its `kind` is its entity type: the RULES.txt section it follows, and what
    IS(e, kind) checks. Rules set velocity, facing, timers and flags; move()
    then applies the velocity with tile collision.
    """

    def __init__(self, kind, x, y, images, anim_rate, hitbox_scale, coyote_frames=0):
        self.kind = kind
        self.images = images              # facing (1 / -1) -> list of animation frames
        self.anim_rate = anim_rate
        self.hitbox_scale = hitbox_scale
        self.rect = images[1][0].get_rect(topleft=(x, y))
        self.fx, self.fy = float(x), float(y)
        self.home = (x, y)
        self.vx = self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.supported = False            # set by STAND_ON; counts as on_ground after move()
        self.coyote_frames = coyote_frames
        self.coyote = 0                   # frames of coyote time left
        self.timers = {}                  # name -> frames left, set by COOLDOWN
        self.vars = {}                    # rule-made vars (SET/ADD/CHECK), default 0
        self.age = 0                      # frames since spawn
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
        self.dead = False
        self.owner = None                 # set by SPAWN(type, owner), read by OWNER(o)
        self.contacts = []                # entities and tiles touching us, sensed each frame (COLLIDE)
        self.step = None                  # [from x, from y, to x, to y, frames, done] while a STEP glides

    @property
    def hitbox(self):
        if self.hitbox_scale == 1:
            return self.rect
        hb = pygame.Rect(0, 0, round(self.rect.w * self.hitbox_scale), round(self.rect.h * self.hitbox_scale))
        hb.center = self.rect.center
        return hb

    def move(self, solids):
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
        if self.step is not None:
            self.glide(solids)
        else:
            self.physics(solids)
        for name in self.timers:
            self.timers[name] = max(0, self.timers[name] - 1)
        self.age += 1

    def glide(self, solids):
        """A STEP in progress: slide toward the target cell, ignoring velocity."""
        sx, sy, tx, ty, n, i = self.step
        i += 1
        t = i / n
        self.fx, self.fy = sx + (tx - sx) * t, sy + (ty - sy) * t
        self.rect.topleft = (round(self.fx), round(self.fy))
        self.vx = self.vy = 0.0
        self.step = None if i >= n else [sx, sy, tx, ty, n, i]
        self.on_ground = self.rect.move(0, 1).collidelist(solids) != -1

    def physics(self, solids):
        # Horizontal move + collide
        self.fx += self.vx
        self.rect.x = round(self.fx)
        for s in solids:
            if self.rect.colliderect(s):
                if self.vx > 0:
                    self.rect.right = s.left
                elif self.vx < 0:
                    self.rect.left = s.right
                self.fx = self.rect.x

        # Vertical move + collide
        self.fy += self.vy
        self.rect.y = round(self.fy)
        self.on_ground = False
        for s in solids:
            if self.rect.colliderect(s):
                if self.vy > 0:
                    self.rect.bottom = s.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = s.bottom
                self.vy = 0
                self.fy = self.rect.y
        # Gravity weaker than 1px/frame may not move us into the floor this
        # frame, so also look 1px down. Without this, on_ground flickers.
        if not self.on_ground and self.vy >= 0 and self.rect.move(0, 1).collidelist(solids) != -1:
            self.on_ground = True
            self.vy = 0
            self.fy = self.rect.y
        if self.supported:                # standing on an entity (STAND_ON)
            self.on_ground = True
            self.supported = False
        # Coyote time: stay "on the ground" for a few frames after walking off
        # a ledge. Moving upward (a jump, a bounce) ends it at once.
        if self.on_ground:
            self.coyote = self.coyote_frames
        elif self.vy < 0:
            self.coyote = 0
        elif self.coyote > 0:
            self.coyote -= 1
            self.on_ground = True

    def draw(self, screen, cam):
        cx, cy = cam
        frames = self.images[self.facing]
        screen.blit(frames[(self.age // self.anim_rate) % len(frames)], (self.rect.x - cx, self.rect.y - cy))


class Tile:
    """A level tile. Plain '#' tiles have type _tile; a [name: tile] section in
    RULES.txt defines more tile types, placed with LEGEND letters.

    Entities see tiles through COLLIDE and IS(e, type), and IS(e, _tile) is
    true for every tile. e(DIE) on a tile removes it. Tiles don't run rules or
    move; effects that change velocity, facing or position on a tile do nothing.
    A tile with solid=0 is drawn and sensed but doesn't block movement.
    """
    is_tile = True
    static = True

    def __init__(self, c, r, kind="_tile", sprite=None, solid=True):
        self.kind, self.solid = kind, solid
        sprite = sprite or SPRITES["ground"]
        self.image = sprite["images"][1][0]
        self.top_image = sprite.get("top")     # drawn instead when no solid tile is above
        self.step = None
        self.c, self.r = c, r
        self.rect = pygame.Rect(c * TILE, r * TILE, TILE, TILE)
        self.hitbox = self.rect
        self.home = self.rect.topleft
        self.fx, self.fy = float(self.rect.x), float(self.rect.y)
        self.vx = self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.timers = {}
        self.vars = {}
        self.age = 0
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
        self.dead = False
        self.owner = None
        self.contacts = []


def sprite(frames, offset=(0, 0), anim_rate=1, hitbox=1.0, flip=None, top=None):
    """A library entry. frames: animation frames facing right; flip: frames
    facing left (default: the same frames); top: tile variant drawn when
    nothing solid sits on top."""
    return dict(images={1: frames, -1: flip or frames}, offset=offset, anim_rate=anim_rate,
                hitbox=hitbox, top=top)


def build_sprites():
    """The sprite library. Any entity or tile type can use any of these with
    [type: sprite=name]; without it, a type uses the sprite with its own name,
    or a pink placeholder. Needs a display (pygame surfaces)."""
    return {
        "player": sprite([make_player_sprite(1)], offset=(4, 2), flip=[make_player_sprite(-1)]),
        "walker": sprite([make_walker_sprite(0), make_walker_sprite(1)], anim_rate=10, hitbox=HITBOX_SCALE),
        "flyer": sprite([make_flyer_sprite(0), make_flyer_sprite(1)], anim_rate=6, hitbox=HITBOX_SCALE),
        "bullet": sprite([make_bullet_sprite()]),
        "turret": sprite([make_turret_sprite(1)], offset=(2, 4), hitbox=HITBOX_SCALE,
                         flip=[make_turret_sprite(-1)]),
        "orb": sprite([make_orb_sprite(0), make_orb_sprite(1)], anim_rate=12),
        "spikes": sprite([make_spikes_sprite()], hitbox=0.5),
        # tiles (also usable by entities)
        "ground": sprite([make_tile()], top=make_grass_tile()),
        "brick": sprite([make_brick_tile()]),
        "water": sprite([make_water_tile()]),
    }


SPRITES = {}   # filled by Game() once pygame is up


# ---------------------------------------------------------------- worlds
class LevelError(Exception):
    pass


def load_level(path):
    """Parse a level.txt into (rows, legend). legend: letter -> type."""
    legend = dict(DEFAULT_LEGEND)
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n").rstrip()
            if line.startswith("//"):
                continue
            if line.upper().startswith("LEGEND "):
                letter, sep, rest = line[7:].partition(":")
                letter, words = letter.strip(), rest.split()
                if "as" in words:
                    raise LevelError(f"{path.name} line {lineno}: 'as' moved to RULES.txt: "
                                     f"write [type: sprite=look] there")
                if not (sep and len(letter) == 1 and letter not in "#." and len(words) == 1):
                    raise LevelError(f"{path.name} line {lineno}: expected 'LEGEND X: type'")
                legend[letter] = words[0]
                continue
            if line:
                rows.append(line)
    if not rows:
        raise LevelError(f"{path.name}: no map rows")
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, ".") for r in rows]
    starts = sum(r.count(ch) for r in rows for ch, kind in legend.items() if kind == "player")
    if starts != 1:
        raise LevelError(f"{path.name}: needs exactly one player start, found {starts}")
    unknown = {ch for r in rows for ch in r if ch not in legend and ch not in "#."}
    if unknown:
        raise LevelError(f"{path.name}: unknown map letters {''.join(sorted(unknown))} (add LEGEND lines)")
    return rows, legend


def list_worlds():
    """[(name, folder)]: the base world first, then every worlds/<name> with both files."""
    out = [(BASE_WORLD, BASE_DIR)]
    if WORLDS_DIR.is_dir():
        for d in sorted(WORLDS_DIR.iterdir()):
            if d.is_dir() and (d / "level.txt").is_file() and (d / "RULES.txt").is_file():
                out.append((d.name, d))
    return out


def world_dir(name):
    for n, d in list_worlds():
        if n == name:
            return d
    return None


# ---------------------------------------------------------------- game
class Game:
    def __init__(self, world_name=BASE_WORLD):
        if not SPRITES:
            SPRITES.update(build_sprites())
        self.message, self.message_timer = "", 0
        self.menu = None              # None, or index of the highlighted world
        self.deaths = 0
        self.input = rules.Input({}, BUFFER_FRAMES)
        self.load_world(world_name, strict=True)

    # --- worlds
    def load_world(self, name, strict=False):
        """Load level + rules together. On error: raise if strict, else keep the current world."""
        folder = world_dir(name)
        try:
            if folder is None:
                names = ", ".join(n for n, _ in list_worlds())
                raise LevelError(f"no world named {name!r}. Worlds: {names}")
            rows, legend = load_level(folder / "level.txt")
            types = set(ENGINE_TYPES) | set(legend.values())
            ruleset = rules.load_rules(folder / "RULES.txt", types, set(SPRITES))
            if ruleset.is_tile("player"):
                raise LevelError("[player] can't be a tile type")
        except (LevelError, rules.RuleError, OSError) as err:
            if strict:
                raise
            self.show_message(f"{name}: {err}")
            return False
        changed = name != getattr(self, "world_name", None)
        self.world_name, self.folder = name, folder
        self.level, self.legend, self.rules = rows, legend, ruleset
        self.placeholders = {}
        self.input.bindings = ruleset.bindings
        self.input.buffers = ruleset.buffers
        self.input.clear()
        self.level_w = len(rows[0]) * TILE
        self.level_h = len(rows) * TILE
        self.rows = len(rows)
        if changed:
            self.deaths = 0
        pygame.display.set_caption(f"Platformer - {name}")
        self.reset()
        return True

    def show_message(self, text):
        print(text)
        self.message, self.message_timer = text, 4 * FPS

    # --- entities
    def sprite_for(self, kind):
        """A type's sprite: its sprite= option, else the sprite named like the type."""
        name = self.rules.options.get(kind, {}).get("sprite", kind)
        if name in SPRITES:
            return SPRITES[name]
        if kind not in self.placeholders:
            self.placeholders[kind] = sprite([make_placeholder_sprite()])
        return self.placeholders[kind]

    def make_entity(self, kind, x, y):
        k = self.sprite_for(kind)
        hitbox = self.rules.options.get(kind, {}).get("hitbox", k["hitbox"])
        ox, oy = k["offset"]
        return Entity(kind, x + ox, y + oy, k["images"], k["anim_rate"], hitbox,
                      COYOTE_FRAMES if kind == "player" else 0)

    def make_tile(self, kind, c, r):
        if kind == "_tile":
            return Tile(c, r)
        solid = self.rules.options.get(kind, {}).get("solid", True)
        return Tile(c, r, kind, self.sprite_for(kind), solid)

    def spawn(self, kind, spawner, owner):
        """SPAWN: a new entity just in front of the spawner, facing the same way.

        It joins the world after this frame's movement and runs its START
        rules next frame.
        """
        ent = self.make_entity(kind, 0, 0)
        r = ent.rect
        if spawner.facing > 0:
            r.left = spawner.rect.right
        else:
            r.right = spawner.rect.left
        r.centery = spawner.rect.centery
        ent.fx, ent.fy = float(r.x), float(r.y)
        ent.home = r.topleft
        ent.prev_bottom, ent.prev_top = r.bottom, r.top
        ent.facing = spawner.facing
        ent.owner = owner
        self.spawned.append(ent)

    def solid_at(self, px, py):
        return self.cell_solid(int(px // TILE), int(py // TILE))

    # --- grid (cells are tiles; r counts screen rows from the top)
    def cell_solid(self, c, r):
        t = self.tiles.get((c, r))
        return t is not None and t.solid

    def cell_of(self, ent):
        """The cell holding an entity's bottom-center point."""
        return ent.rect.centerx // TILE, (ent.rect.bottom - 1) // TILE

    def cell_topleft(self, ent, c, r):
        """Where an entity's rect goes to sit in a cell: centered, on the cell's floor."""
        return c * TILE + (TILE - ent.rect.w) / 2, (r + 1) * TILE - ent.rect.h

    def entities(self):
        return [self.player] + self.others

    def tiles_in(self, rect):
        """Tiles overlapping rect, looked up through the grid."""
        out = []
        for r in range(rect.top // TILE, (rect.bottom - 1) // TILE + 1):
            for c in range(rect.left // TILE, (rect.right - 1) // TILE + 1):
                t = self.tiles.get((c, r))
                if t is not None:
                    out.append(t)
        return out

    def reset(self):
        self.grid = [list(row) for row in self.level]
        self.tiles, self.others, self.spawned = {}, [], []
        for r, row in enumerate(self.level):
            for c, ch in enumerate(row):
                x, y = c * TILE, r * TILE
                kind = "_tile" if ch == "#" else self.legend.get(ch)
                if kind is None:
                    continue
                if kind == "_tile" or self.rules.is_tile(kind):
                    self.tiles[(c, r)] = self.make_tile(kind, c, r)
                else:
                    ent = self.make_entity(kind, x, y)
                    if ent.kind == "player":
                        self.player = ent
                    else:
                        self.others.append(ent)
        self.solids = [t.rect for t in self.tiles.values() if t.solid]
        self.update_camera()

    def kill_player(self):
        self.deaths += 1
        self.reset()

    # --- input
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if self.menu is not None:
                self.menu_key(e.key)
            elif e.key == pygame.K_r:
                if self.load_world(self.world_name):
                    self.show_message("Reloaded")
            elif e.key == pygame.K_p:
                self.open_menu()
            else:
                self.input.press(e.key)
        elif e.type == pygame.KEYUP:
            self.input.release(e.key)

    def open_menu(self):
        names = [n for n, _ in list_worlds()]
        self.menu = names.index(self.world_name) if self.world_name in names else 0

    def menu_key(self, key):
        worlds = list_worlds()
        if key in (pygame.K_UP, pygame.K_w):
            self.menu = (self.menu - 1) % len(worlds)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu = (self.menu + 1) % len(worlds)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.load_world(worlds[self.menu % len(worlds)][0]):
                self.menu = None
        elif key in (pygame.K_ESCAPE, pygame.K_p):
            self.menu = None
        self.input.clear()

    # --- simulation
    def sense(self):
        """Fill each entity's contacts from where things ended up last frame.

        Entities touch when their hitboxes overlap. Tiles touch when they are
        within 1px of the entity's sprite rect (physics keeps them from
        overlapping, so standing on the ground counts as touching it).
        """
        ents = self.entities()
        for e in ents:
            e.contacts = []
        for i, a in enumerate(ents):
            ha = a.hitbox
            for b in ents[i + 1:]:
                if ha.colliderect(b.hitbox):
                    a.contacts.append(b)
                    b.contacts.append(a)
            a.contacts.extend(self.tiles_in(a.rect.inflate(2, 2)))

    def update(self):
        if self.menu is not None:
            return
        p = self.player
        self.input.held = pygame.key.get_pressed()
        self.sense()
        for ent in self.entities():
            if not ent.dead:              # something earlier this frame may have killed it
                self.rules.run(ent.kind, ent, self)
        self.input.end_frame()

        if p.dead:
            self.kill_player()
            return
        self.others = [e for e in self.others if not e.dead]
        dead_tiles = [key for key, t in self.tiles.items() if t.dead]
        for c, r in dead_tiles:
            del self.tiles[(c, r)]
            self.grid[r][c] = "."
        if dead_tiles:
            self.solids = [t.rect for t in self.tiles.values() if t.solid]

        for ent in self.entities():
            ent.move(self.solids)
        self.others += self.spawned
        self.spawned = []
        self.update_camera()

    def update_camera(self):
        p = self.player.rect
        self.cam = (max(0, min(p.centerx - SCREEN_W // 2, self.level_w - SCREEN_W)),
                    max(0, min(p.centery - SCREEN_H // 2, self.level_h - SCREEN_H)))

    # --- drawing
    def on_screen(self, rect):
        return rect.move(-self.cam[0], -self.cam[1]).colliderect((0, 0, SCREEN_W, SCREEN_H))

    def draw(self, screen, font):
        cx, cy = self.cam
        screen.fill(SKY)
        for t in self.tiles.values():
            if self.on_screen(t.rect):
                img = t.image
                if t.top_image is not None and not self.cell_solid(t.c, t.r - 1):
                    img = t.top_image
                screen.blit(img, (t.rect.x - cx, t.rect.y - cy))
        for e in self.others:
            if self.on_screen(e.rect):
                e.draw(screen, self.cam)
        self.player.draw(screen, self.cam)
        hud = f"{self.world_name}   Deaths: {self.deaths}   (P: worlds, R: reload)"
        screen.blit(font.render(hud, True, (0, 0, 0)), (10, 8))
        if self.message_timer:
            self.message_timer -= 1
            screen.blit(font.render(self.message, True, (120, 0, 0)), (10, 34))
        if self.menu is not None:
            self.draw_menu(screen, font)

    def draw_menu(self, screen, font):
        worlds = list_worlds()
        h = 70 + 30 * len(worlds)
        box = pygame.Rect(0, 0, 360, h)
        box.center = (SCREEN_W // 2, SCREEN_H // 2)
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (245, 245, 235), box, border_radius=8)
        pygame.draw.rect(screen, (0, 0, 0), box, 2, border_radius=8)
        screen.blit(font.render("Choose a world", True, (0, 0, 0)), (box.x + 20, box.y + 14))
        for i, (name, _) in enumerate(worlds):
            y = box.y + 48 + 30 * i
            if i == self.menu:
                pygame.draw.rect(screen, (255, 220, 120), (box.x + 10, y - 3, box.w - 20, 26), border_radius=4)
            label = name + ("  (current)" if name == self.world_name else "")
            screen.blit(font.render(label, True, (0, 0, 0)), (box.x + 24, y))
        tip = font.render("Up/Down, Enter to play, Esc to close", True, (90, 90, 90))
        screen.blit(tip, (box.x + 20, box.bottom - 26))


def main():
    parser = argparse.ArgumentParser(description="Rule-driven platformer")
    parser.add_argument("-w", "--world", default=BASE_WORLD,
                        help=f"world to load: a folder in worlds/, or '{BASE_WORLD}' (default)")
    parser.add_argument("-p", "--pick", action="store_true", help="start at the world select list")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    try:
        game = Game(args.world)
    except (LevelError, rules.RuleError, OSError) as err:
        print(f"Can't load world {args.world!r}: {err}")
        pygame.quit()
        sys.exit(1)
    if args.pick:
        game.open_menu()

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and game.menu is None:
                running = False
            else:
                game.handle_event(e)
        game.update()
        game.draw(screen, font)
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()


if __name__ == "__main__":
    main()
