"""Minimal 2D platformer / shooter in a single pygame script.

All entity behavior (player controls, enemy movement, what kills what) comes
from the rules in RULES.txt; see rules.py for the grammar. The engine only
moves things, collides them with tiles, and senses contacts. With the default
rules:
    Move   - Arrow keys or A / D
    Jump   - Space (or W / Up / Z / K). Hold for a higher jump.
    Shoot  - J (or X). Fires in the direction you're facing.
    R      - Reload RULES.txt and restart the level
    Esc    - Quit

Touching an enemy or falling into a pit kills you (the level restarts).
Shoot enemies, or stomp them by landing on top.
"""
import sys
from pathlib import Path

import pygame

import rules

# ---------------------------------------------------------------- settings
TILE = 32
SCREEN_W, SCREEN_H = 800, 480
FPS = 60

RULES_PATH = Path(__file__).with_name("RULES.txt")

ENGINE_TYPES = ("_tile",)  # entity types the engine provides, usable in IS(e, type)

HITBOX_SCALE = 0.7        # enemy hitbox size relative to its sprite, centered

# '#' = solid tile; other letters spawn entities (see build_kinds)
# Gaps in the bottom rows are bottomless pits.
LEVEL = [
    "#..................................................................................................#",
    "#..................................................................................................#",
    "#..................................................................................................#",
    "#..................................................................................................#",
    "#..................................................................................................#",
    "#...................................................................F..............................#",
    "#.....................................F................####........................................#",
    "#............####...............####.........................F..##...........####..................#",
    "#...................F.............................G.....................................F..........#",
    "#..........................G....................######..................G.............##...........#",
    "#.......####.............#####...........##...........................######.......................#",
    "#....................................#.............................................................#",
    "#..P..........G...............G......#.........G.........G......................G.............G....#",
    "##################....##################....################.......##################.....##########",
    "##################....##################....################.......##################.....##########",
]

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


# ---------------------------------------------------------------- entities
class Entity:
    """Anything with rules: the player and every enemy.

    Its `kind` is its entity type: the RULES.txt section it follows, and what
    IS(e, kind) checks. Rules set velocity, facing, timers and flags; move()
    then applies the velocity with tile collision.
    """

    def __init__(self, kind, x, y, images, anim_rate, hitbox_scale):
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
        self.timers = {}                  # name -> frames left, set by COOLDOWN
        self.age = 0                      # frames since spawn
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
        self.dead = False
        self.owner = None                 # set by SPAWN(type, owner), read by OWNER(o)
        self.contacts = []                # entities and tiles touching us, sensed each frame (COLLIDE)

    @property
    def hitbox(self):
        if self.hitbox_scale == 1:
            return self.rect
        hb = pygame.Rect(0, 0, int(self.rect.w * self.hitbox_scale), int(self.rect.h * self.hitbox_scale))
        hb.center = self.rect.center
        return hb

    def move(self, solids):
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
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

        for name in self.timers:
            self.timers[name] = max(0, self.timers[name] - 1)
        self.age += 1

    def draw(self, screen, cam):
        frames = self.images[self.facing]
        screen.blit(frames[(self.age // self.anim_rate) % len(frames)], (self.rect.x - cam, self.rect.y))


class Tile:
    """A solid level tile: an entity of type _tile.

    Entities see tiles through COLLIDE and IS(e, _tile), and e(DIE) on a tile
    removes it. Tiles don't run rules or move; effects that change velocity
    or facing on a tile do nothing.
    """
    kind = "_tile"

    def __init__(self, c, r):
        self.c, self.r = c, r
        self.rect = pygame.Rect(c * TILE, r * TILE, TILE, TILE)
        self.hitbox = self.rect
        self.home = self.rect.topleft
        self.fx, self.fy = float(self.rect.x), float(self.rect.y)
        self.vx = self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.timers = {}
        self.age = 0
        self.prev_bottom = self.rect.bottom
        self.prev_top = self.rect.top
        self.dead = False
        self.owner = None
        self.contacts = []


# Level letter -> entity type
LEGEND = {"P": "player", "G": "walker", "F": "flyer"}


def build_kinds():
    """Entity type -> how it looks. Types in RULES.txt that aren't here get a placeholder."""
    walker = [make_walker_sprite(0), make_walker_sprite(1)]
    flyer = [make_flyer_sprite(0), make_flyer_sprite(1)]
    bullet = [make_bullet_sprite()]
    return {
        "player": dict(offset=(4, 2), anim_rate=1, hitbox_scale=1,
                       images={1: [make_player_sprite(1)], -1: [make_player_sprite(-1)]}),
        "walker": dict(offset=(0, 0), anim_rate=10, hitbox_scale=HITBOX_SCALE,
                       images={1: walker, -1: walker}),
        "flyer": dict(offset=(0, 0), anim_rate=6, hitbox_scale=HITBOX_SCALE,
                      images={1: flyer, -1: flyer}),
        "bullet": dict(offset=(0, 0), anim_rate=1, hitbox_scale=1,
                       images={1: bullet, -1: bullet}),
    }


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        self.tile_img = make_tile()
        self.grass_img = make_grass_tile()
        self.kinds = build_kinds()
        self.level_w = len(LEVEL[0]) * TILE
        self.level_h = len(LEVEL) * TILE
        self.deaths = 0
        self.rules = self.load_rules()
        self.input = rules.Input(self.rules.bindings)
        self.message, self.message_timer = "", 0
        self.reset()

    def load_rules(self):
        return rules.load_rules(RULES_PATH, set(ENGINE_TYPES) | set(self.kinds))

    def reload_rules(self):
        try:
            self.rules = self.load_rules()
        except (rules.RuleError, OSError) as err:
            self.show_message(f"RULES.txt error, kept old rules: {err}")
            return
        self.input.bindings = self.rules.bindings
        self.show_message("Rules reloaded")
        self.reset()

    def show_message(self, text):
        print(text)
        self.message, self.message_timer = text, 4 * FPS

    def make_entity(self, kind, x, y):
        k = self.kinds.get(kind)
        if k is None:
            img = make_placeholder_sprite()
            k = self.kinds[kind] = dict(offset=(0, 0), anim_rate=1, hitbox_scale=1,
                                        images={1: [img], -1: [img]})
        ox, oy = k["offset"]
        return Entity(kind, x + ox, y + oy, k["images"], k["anim_rate"], k["hitbox_scale"])

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
        c, r = int(px // TILE), int(py // TILE)
        if 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0]):
            return self.grid[r][c] == "#"
        return False

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
        self.grid = [list(row) for row in LEVEL]
        self.tiles, self.others, self.spawned = {}, [], []
        for r, row in enumerate(LEVEL):
            for c, ch in enumerate(row):
                x, y = c * TILE, r * TILE
                if ch == "#":
                    self.tiles[(c, r)] = Tile(c, r)
                elif ch in LEGEND:
                    ent = self.make_entity(LEGEND[ch], x, y)
                    if ent.kind == "player":
                        self.player = ent
                    else:
                        self.others.append(ent)
        self.solids = [t.rect for t in self.tiles.values()]
        self.cam = 0

    def kill_player(self):
        self.deaths += 1
        self.reset()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.reload_rules()
            else:
                self.input.pressed.add(e.key)
        elif e.type == pygame.KEYUP:
            self.input.released.add(e.key)

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
        p = self.player
        self.input.held = pygame.key.get_pressed()
        self.sense()
        for ent in self.entities():
            if not ent.dead:              # something earlier this frame may have killed it
                self.rules.run(ent.kind, ent, self)
        self.input.pressed.clear()
        self.input.released.clear()

        if p.dead:
            self.kill_player()
            return
        self.others = [e for e in self.others if not e.dead]
        dead_tiles = [key for key, t in self.tiles.items() if t.dead]
        for c, r in dead_tiles:
            del self.tiles[(c, r)]
            self.grid[r][c] = "."
        if dead_tiles:
            self.solids = [t.rect for t in self.tiles.values()]

        for ent in self.entities():
            ent.move(self.solids)
        self.others += self.spawned
        self.spawned = []

        target = p.rect.centerx - SCREEN_W // 2
        self.cam = max(0, min(target, self.level_w - SCREEN_W))

    def draw(self, screen, font):
        screen.fill(SKY)
        for t in self.tiles.values():
            if -TILE < t.rect.x - self.cam < SCREEN_W:
                top = t.r == 0 or self.grid[t.r - 1][t.c] != "#"
                screen.blit(self.grass_img if top else self.tile_img, (t.rect.x - self.cam, t.rect.y))
        for e in self.others:
            if -TILE * 2 < e.rect.x - self.cam < SCREEN_W:
                e.draw(screen, self.cam)
        self.player.draw(screen, self.cam)
        screen.blit(font.render(f"Deaths: {self.deaths}", True, (0, 0, 0)), (10, 8))
        if self.message_timer:
            self.message_timer -= 1
            screen.blit(font.render(self.message, True, (120, 0, 0)), (10, 34))


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Platformer")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    try:
        game = Game()
    except rules.RuleError as err:
        print(f"RULES.txt error: {err}")
        pygame.quit()
        sys.exit(1)

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
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
