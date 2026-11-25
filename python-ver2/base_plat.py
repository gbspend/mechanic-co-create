"""Minimal 2D platformer / shooter in a single pygame script.

Controls:
    Move   - Arrow keys or A / D
    Jump   - Space (or W / Up / Z). Hold for a higher jump.
    Shoot  - J (or X). Fires in the direction you're facing.
    Esc    - Quit

Touching an enemy or falling into a pit kills you (the level restarts).
Shoot enemies, or stomp them by landing on top.
"""
import math
import pygame

# ---------------------------------------------------------------- settings
TILE = 32
SCREEN_W, SCREEN_H = 800, 480
FPS = 60

GRAVITY = 0.6
JUMP_GRAVITY = 0.3        # weaker gravity while rising with jump held
MAX_FALL = 12
MOVE_SPEED = 4
JUMP_SPEED = 10
STOMP_BOUNCE = 8
BULLET_SPEED = 10
BULLET_RANGE = 450
SHOOT_COOLDOWN = 15       # frames

HITBOX_SCALE = 0.7        # enemy hitbox size relative to its sprite, centered

JUMP_KEYS = (pygame.K_SPACE, pygame.K_w, pygame.K_UP, pygame.K_z, pygame.K_k)
SHOOT_KEYS = (pygame.K_j, pygame.K_x)

# '#' = solid tile, 'P' = player start, 'G' = ground patroller, 'F' = flyer
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


def centered_hitbox(sprite_rect):
    hb = pygame.Rect(0, 0, int(sprite_rect.w * HITBOX_SCALE), int(sprite_rect.h * HITBOX_SCALE))
    hb.center = sprite_rect.center
    return hb


# ---------------------------------------------------------------- entities
class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 24, 30)
        self.vx = self.vy = 0.0
        self.fx, self.fy = float(x), float(y)
        self.facing = 1
        self.on_ground = False
        self.cooldown = 0
        self.sprites = {1: make_player_sprite(1), -1: make_player_sprite(-1)}

    def update(self, keys, solids):
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        jump_held = any(keys[k] for k in JUMP_KEYS)

        self.vx = (right - left) * MOVE_SPEED
        if self.vx:
            self.facing = 1 if self.vx > 0 else -1

        # Mario-style variable jump: weak gravity while rising and holding jump.
        g = JUMP_GRAVITY if (jump_held and self.vy < 0) else GRAVITY
        self.vy = min(self.vy + g, MAX_FALL)

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

        if self.cooldown:
            self.cooldown -= 1

    def jump(self):
        if self.on_ground:
            self.vy = -JUMP_SPEED
            self.on_ground = False

    def draw(self, screen, cam):
        screen.blit(self.sprites[self.facing], (self.rect.x - cam, self.rect.y))


class Walker:
    """Ground patroller: walks back and forth, turning at walls and ledges."""
    SPEED = 1.2

    def __init__(self, x, y):
        self.frames = [make_walker_sprite(0), make_walker_sprite(1)]
        self.rect = self.frames[0].get_rect(topleft=(x, y))
        self.fx = float(x)
        self.vy = 0.0
        self.dir = -1
        self.t = 0

    @property
    def hitbox(self):
        return centered_hitbox(self.rect)

    def update(self, solids, solid_at):
        self.t += 1
        # Gravity
        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        self.rect.y += round(self.vy)
        for s in solids:
            if self.rect.colliderect(s) and self.vy > 0:
                self.rect.bottom = s.top
                self.vy = 0
        # Walk, turning at walls or ledges
        self.fx += self.dir * self.SPEED
        self.rect.x = round(self.fx)
        ahead_x = self.rect.right if self.dir > 0 else self.rect.left - 1
        wall = solid_at(ahead_x, self.rect.centery)
        ledge = self.vy == 0 and not solid_at(ahead_x, self.rect.bottom + 2)
        if wall or ledge:
            self.dir *= -1

    def draw(self, screen, cam):
        screen.blit(self.frames[(self.t // 10) % 2], (self.rect.x - cam, self.rect.y))


class Flyer:
    """Hovers up and down around its spawn point."""

    def __init__(self, x, y):
        self.frames = [make_flyer_sprite(0), make_flyer_sprite(1)]
        self.rect = self.frames[0].get_rect(topleft=(x, y))
        self.base_y = y
        self.t = 0

    @property
    def hitbox(self):
        return centered_hitbox(self.rect)

    def update(self, solids, solid_at):
        self.t += 1
        self.rect.y = self.base_y + round(math.sin(self.t * 0.04) * 70)

    def draw(self, screen, cam):
        screen.blit(self.frames[(self.t // 6) % 2], (self.rect.x - cam, self.rect.y))


class Bullet:
    def __init__(self, x, y, direction):
        self.rect = pygame.Rect(0, 0, 10, 4)
        self.rect.center = (x, y)
        self.dir = direction
        self.traveled = 0
        self.alive = True

    def update(self, solids):
        self.rect.x += self.dir * BULLET_SPEED
        self.traveled += BULLET_SPEED
        if self.traveled > BULLET_RANGE or self.rect.collidelist(solids) != -1:
            self.alive = False

    def draw(self, screen, cam):
        pygame.draw.rect(screen, (255, 240, 80), self.rect.move(-cam, 0))


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        self.tile_img = make_tile()
        self.grass_img = make_grass_tile()
        self.grid = [list(row) for row in LEVEL]
        self.level_w = len(LEVEL[0]) * TILE
        self.level_h = len(LEVEL) * TILE
        self.deaths = 0
        self.reset()

    def solid_at(self, px, py):
        c, r = int(px // TILE), int(py // TILE)
        if 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0]):
            return self.grid[r][c] == "#"
        return False

    def reset(self):
        self.solids, self.tiles, self.enemies, self.bullets = [], [], [], []
        for r, row in enumerate(LEVEL):
            for c, ch in enumerate(row):
                x, y = c * TILE, r * TILE
                if ch == "#":
                    rect = pygame.Rect(x, y, TILE, TILE)
                    self.solids.append(rect)
                    top = r == 0 or LEVEL[r - 1][c] != "#"
                    self.tiles.append((rect, self.grass_img if top else self.tile_img))
                elif ch == "P":
                    self.player = Player(x + 4, y + 2)
                elif ch == "G":
                    self.enemies.append(Walker(x, y))
                elif ch == "F":
                    self.enemies.append(Flyer(x, y))
        self.cam = 0

    def kill_player(self):
        self.deaths += 1
        self.reset()

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in JUMP_KEYS:
                self.player.jump()
            elif e.key in SHOOT_KEYS and self.player.cooldown == 0:
                p = self.player
                x = p.rect.right if p.facing > 0 else p.rect.left
                self.bullets.append(Bullet(x, p.rect.y + 16, p.facing))
                p.cooldown = SHOOT_COOLDOWN

    def update(self):
        p = self.player
        prev_bottom = p.rect.bottom
        p.update(pygame.key.get_pressed(), self.solids)

        if p.rect.top > self.level_h:          # fell into a pit
            self.kill_player()
            return

        for e in self.enemies:
            e.update(self.solids, self.solid_at)
        self.enemies = [e for e in self.enemies if e.rect.top < self.level_h]

        for b in self.bullets:
            b.update(self.solids)
            for e in self.enemies:
                if b.alive and b.rect.colliderect(e.hitbox):
                    b.alive = False
                    self.enemies.remove(e)
                    break
        self.bullets = [b for b in self.bullets if b.alive]

        for e in list(self.enemies):
            hb = e.hitbox
            if p.rect.colliderect(hb):
                # Stomp if falling and we were above the hitbox last frame.
                if p.vy > 0 and prev_bottom <= hb.top + 6:
                    self.enemies.remove(e)
                    p.vy = -STOMP_BOUNCE
                    p.fy = p.rect.y
                else:
                    self.kill_player()
                    return

        target = p.rect.centerx - SCREEN_W // 2
        self.cam = max(0, min(target, self.level_w - SCREEN_W))

    def draw(self, screen, font):
        screen.fill(SKY)
        for rect, img in self.tiles:
            if -TILE < rect.x - self.cam < SCREEN_W:
                screen.blit(img, (rect.x - self.cam, rect.y))
        for e in self.enemies:
            e.draw(screen, self.cam)
        for b in self.bullets:
            b.draw(screen, self.cam)
        self.player.draw(screen, self.cam)
        screen.blit(font.render(f"Deaths: {self.deaths}", True, (0, 0, 0)), (10, 8))


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Platformer")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    game = Game()

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
