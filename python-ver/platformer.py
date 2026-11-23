"""Small side-scrolling platformer demo (original level) built with pygame.

Controls: arrows / A,D move - Space / Z / Up jump - Shift / X run - R restart - Esc quit
"""
import math
import sys

import pygame

# --- screen / tiles ---------------------------------------------------------
T = 48                       # tile size in pixels (16px art scaled x3)
COLS_VIEW, ROWS = 16, 14
SW, SH = T * COLS_VIEW, T * ROWS
FPS = 60

# --- physics (pixels per frame) ---------------------------------------------
WALK_MAX, RUN_MAX = 4.5, 7.5
ACCEL, RUN_ACCEL = 0.22, 0.32
FRICTION, SKID = 0.25, 0.6
GRAV_HOLD, GRAV = 0.38, 1.1   # low gravity while rising with jump held
MAX_FALL = 13
JUMP_V = 12.5
STOMP_BOUNCE = 9.0
ENEMY_SPEED, SHELL_SPEED = 1.5, 8.5

PLAYER_W, SMALL_H, BIG_H = 36, 42, 90
HITBOX_SCALE = 0.7            # enemy interaction box vs. sprite size

STOMP_PTS = [100, 200, 400, 800, 1000, 2000, 4000, 8000]
SHELL_PTS = [500, 800, 1000, 2000, 4000, 8000]

SOLID = set("#BS?MNpU")
JUMP_KEYS = (pygame.K_SPACE, pygame.K_z, pygame.K_UP, pygame.K_w)

# --- colours ----------------------------------------------------------------
SKY = (100, 160, 250)
GROUND, GROUND_DARK = (190, 110, 50), (120, 60, 20)
BRICK, MORTAR = (180, 80, 40), (60, 25, 10)
QBLOCK, QDARK = (245, 170, 40), (150, 80, 10)
USED = (140, 95, 50)
STAIR, STAIR_LIGHT = (150, 120, 90), (200, 170, 140)
PIPE, PIPE_DARK, PIPE_LIGHT = (40, 170, 60), (15, 80, 25), (140, 230, 120)
HAT, SHIRT, PANTS, SKIN, BOOT = (20, 150, 140), (20, 150, 140), (40, 40, 110), (250, 200, 160), (90, 50, 20)
BEETLE = (170, 40, 60)
ARMOR, ARMOR_RIM, LIZARD = (50, 90, 200), (190, 210, 250), (240, 210, 90)
GOLD, GOLD_DARK = (255, 210, 40), (180, 120, 0)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)

# --- level ------------------------------------------------------------------
LEVEL_W = 112
PITS = [(46, 47), (62, 64)]
CHECK_X = 107 * T + T // 2
ENEMIES = [("g", 20, 11), ("g", 27, 11), ("g", 34, 11), ("g", 36, 11), ("k", 44, 11),
           ("g", 54, 3), ("g", 56, 3), ("g", 72, 11), ("g", 74, 11), ("k", 78, 11),
           ("g", 84, 11), ("g", 86, 11)]


def build_level():
    """Tiles: # ground, B brick, N multi-coin brick, ? coin block, M grow block,
    U used block, S stair block, p pipe."""
    g = [[" "] * LEVEL_W for _ in range(ROWS)]

    def put(x, y, ch):
        g[y][x] = ch

    def row(x0, y, chars):
        for i, ch in enumerate(chars):
            put(x0 + i, y, ch)

    for x in range(LEVEL_W):
        if not any(a <= x <= b for a, b in PITS):
            put(x, 12, "#")
            put(x, 13, "#")
    put(10, 8, "?")
    row(14, 8, "B?M?B")
    put(16, 4, "?")
    for col, h in ((22, 2), (30, 3), (38, 4)):
        for y in range(12 - h, 12):
            put(col, y, "p")
            put(col + 1, y, "p")
    row(50, 8, "B?B")
    row(52, 4, "BBBB?BBB")
    row(66, 8, "BBNB")
    put(67, 4, "?")
    for x in (74, 77, 80):
        put(x, 8, "?")
    put(77, 4, "?")
    row(86, 8, "BBB")
    row(89, 4, "B?B")
    for i in range(4):                      # stairs up, then down
        for y in range(11 - i, 12):
            put(94 + i, y, "S")
            put(103 - i, y, "S")
    return g


class Level:
    def __init__(self):
        self.grid = build_level()
        self.bumps = {}   # (col, row) -> frames of bump animation left
        self.multi = {}   # (col, row) -> [first hit frame, coins given]

    def tile(self, c, r):
        if r < 0 or r >= ROWS:
            return " "
        if c < 0 or c >= LEVEL_W:
            return "#"
        return self.grid[r][c]

    def solid(self, c, r):
        return self.tile(c, r) in SOLID


# --- entities ---------------------------------------------------------------
class Body:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = float(x), float(y), w, h
        self.vx = self.vy = 0.0
        self.on_ground = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def move_x(self, level):
        """Move horizontally; returns True if a wall was hit."""
        self.x += self.vx
        if self.vx == 0:
            return False
        col = int((self.x + self.w - 0.01) // T) if self.vx > 0 else int(self.x // T)
        r0, r1 = int(self.y // T), int((self.y + self.h - 0.01) // T)
        if any(level.solid(col, r) for r in range(r0, r1 + 1)):
            self.x = col * T - self.w if self.vx > 0 else (col + 1) * T
            return True
        return False

    def move_y(self, level):
        """Move vertically; returns list of (col, row) tiles hit."""
        self.y += self.vy
        self.on_ground = False
        if self.vy == 0:
            return []
        r = int((self.y + self.h - 0.01) // T) if self.vy > 0 else int(self.y // T)
        c0, c1 = int(self.x // T), int((self.x + self.w - 0.01) // T)
        hits = [(c, r) for c in range(c0, c1 + 1) if level.solid(c, r)]
        if hits:
            if self.vy > 0:
                self.y = r * T - self.h
                self.on_ground = True
            else:
                self.y = (r + 1) * T
            self.vy = 0
        return hits


class Player(Body):
    def __init__(self):
        super().__init__(3 * T, 12 * T - SMALL_H, PLAYER_W, SMALL_H)
        self.big = False
        self.facing = 1
        self.invuln = 0
        self.chain = 0                      # stomps in a row without landing
        self.prev_bottom = self.y + self.h

    def jump(self):
        if self.on_ground:
            self.vy = -(JUMP_V + abs(self.vx) / RUN_MAX * 1.5)
            self.on_ground = False

    def grow(self):
        if not self.big:
            self.big = True
            self.y -= BIG_H - SMALL_H
            self.h = BIG_H

    def shrink(self):
        self.big = False
        self.y += BIG_H - SMALL_H
        self.h = SMALL_H
        self.invuln = 120

    def update(self, keys, level):
        """Returns tiles hit with the head this frame."""
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_x]
        jump_held = any(keys[k] for k in JUMP_KEYS)
        dirn = int(bool(right)) - int(bool(left))
        top = RUN_MAX if run else WALK_MAX

        if dirn:
            self.facing = dirn
            if self.vx * dirn < 0 and self.on_ground:
                self.vx += dirn * SKID
            else:
                self.vx += dirn * (RUN_ACCEL if run else ACCEL)
        elif self.on_ground:
            self.vx = 0 if abs(self.vx) <= FRICTION else self.vx - math.copysign(FRICTION, self.vx)
        if abs(self.vx) > top:   # releasing run drops straight back to walk speed
            self.vx = math.copysign(top, self.vx)

        g = GRAV_HOLD if jump_held and self.vy < 0 else GRAV
        self.vy = min(self.vy + g, MAX_FALL)

        self.prev_bottom = self.y + self.h
        if self.move_x(level):
            self.vx = 0
        if self.x < 0:
            self.x, self.vx = 0, 0
        going_up = self.vy < 0
        hits = self.move_y(level)
        if self.on_ground:
            self.chain = 0
        return hits if going_up else []


class Enemy(Body):
    def __init__(self, kind, col, row):
        h = 42 if kind == "g" else 66
        super().__init__(col * T + 3, (row + 1) * T - h, 42, h)
        self.kind = kind          # "g" walker, "k" shell enemy
        self.state = "walk"       # walk, flat, shell, slide, dead
        self.vx = -ENEMY_SPEED
        self.active = False
        self.timer = 0
        self.grace = 0            # frames a kicked shell can't hurt the player
        self.chain = 0            # kills by this sliding shell
        self.remove = False

    @property
    def hitbox(self):
        """Interaction box: 70% of the sprite's width and height, centred inside it."""
        w, h = int(self.w * HITBOX_SCALE), int(self.h * HITBOX_SCALE)
        return pygame.Rect(int(self.x + (self.w - w) / 2), int(self.y + (self.h - h) / 2), w, h)

    def set_shell(self):
        bottom = self.y + self.h
        self.h = 42
        self.y = bottom - self.h
        self.state, self.vx = "shell", 0

    def flatten(self):
        self.y += self.h // 2
        self.h //= 2
        self.state, self.vx, self.timer = "flat", 0, 30

    def knock(self, direction):
        self.state = "dead"
        self.vx, self.vy = 2 * direction, -8

    def update(self, level):
        if self.state == "dead":
            self.vy += 0.8
            self.x += self.vx
            self.y += self.vy
            self.remove = self.y > SH
            return
        if self.state == "flat":
            self.timer -= 1
            self.remove = self.timer <= 0
            return
        if self.grace:
            self.grace -= 1
        self.vy = min(self.vy + GRAV, MAX_FALL)
        if self.move_x(level):
            self.vx = -self.vx
        self.move_y(level)
        if self.y > SH:
            self.remove = True


class GrowItem(Body):
    def __init__(self, col, row):
        super().__init__(col * T + 6, row * T + 12, 36, 36)
        self.rise = 32            # frames spent rising out of the block
        self.remove = False

    def update(self, level):
        if self.rise:
            self.y -= 1.5
            self.rise -= 1
            if not self.rise:
                self.vx = 3
            return
        self.vy = min(self.vy + GRAV, MAX_FALL)
        if self.move_x(level):
            self.vx = -self.vx
        self.move_y(level)
        if self.y > SH:
            self.remove = True


# --- game -------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Platformer demo")
        self.screen = pygame.display.set_mode((SW, SH))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 40)
        self.small = pygame.font.Font(None, 30)
        self.big_font = pygame.font.Font(None, 64)
        self.qmark = pygame.font.Font(None, 48).render("?", True, QDARK)
        self.reset()

    def reset(self):
        self.level = Level()
        self.player = Player()
        self.enemies = [Enemy(*e) for e in ENEMIES]
        self.items, self.coins, self.debris, self.popups = [], [], [], []
        self.score = 0
        self.cam = 0
        self.frame = 0
        self.finished = False
        self.dying = 0

    # --- scoring / events ---
    def add_score(self, pts, x, y):
        self.score += pts
        self.popups.append([x, y, str(pts), 45])

    def spawn_coin(self, c, r):
        self.coins.append([c * T + T / 2, r * T, -13.0, 28])   # x, y, vy, life
        self.add_score(200, c * T + 6, r * T - T)

    def stomp_score(self, e):
        p = self.player
        self.add_score(STOMP_PTS[min(p.chain, len(STOMP_PTS) - 1)], e.x, e.y - 20)
        p.chain += 1

    def kick(self, e):
        p = self.player
        d = 1 if p.x + p.w / 2 < e.x + e.w / 2 else -1
        e.state, e.vx, e.grace, e.chain = "slide", d * SHELL_SPEED, 12, 0

    def hurt(self):
        p = self.player
        if p.invuln:
            return
        if p.big:
            p.shrink()
        else:
            self.dying = 90
            p.vy = -14

    def hit_enemies_above(self, c, r):
        for e in self.enemies:
            if (e.state in ("walk", "shell", "slide") and abs(e.y + e.h - r * T) < 8
                    and e.x + e.w > c * T and e.x < (c + 1) * T):
                e.knock(1 if e.x + e.w / 2 > (c + 0.5) * T else -1)
                self.add_score(100, e.x, e.y - 20)

    def bump_block(self, hits):
        p, lv = self.player, self.level
        cx = p.x + p.w / 2
        c, r = min(hits, key=lambda h: abs((h[0] + 0.5) * T - cx))
        t = lv.grid[r][c]
        if t == "?":
            lv.grid[r][c] = "U"
            self.spawn_coin(c, r)
        elif t == "M":
            lv.grid[r][c] = "U"
            self.items.append(GrowItem(c, r))
        elif t == "N":
            info = lv.multi.setdefault((c, r), [self.frame, 0])
            info[1] += 1
            self.spawn_coin(c, r)
            if info[1] >= 10 or self.frame - info[0] > 240:
                lv.grid[r][c] = "U"
        elif t == "B":
            if p.big:
                lv.grid[r][c] = " "
                x, y = c * T, r * T
                for dx, dy, vx, vy in ((0, 0, -3, -12), (24, 0, 3, -12), (0, 24, -3, -8), (24, 24, 3, -8)):
                    self.debris.append([x + dx, y + dy, vx, vy])
                self.add_score(50, x, y - 20)
                self.hit_enemies_above(c, r)
                return
        else:
            return
        lv.bumps[(c, r)] = 8
        self.hit_enemies_above(c, r)

    # --- update ---
    def update(self):
        self.frame += 1
        for pop in self.popups:
            pop[1] -= 1
            pop[3] -= 1
        self.popups = [pop for pop in self.popups if pop[3] > 0]
        if self.finished:
            return
        p = self.player
        if self.dying:
            self.dying -= 1
            p.vy += 0.8
            p.y += p.vy
            if not self.dying:
                self.reset()
            return

        keys = pygame.key.get_pressed()
        head_hits = p.update(keys, self.level)
        if head_hits:
            self.bump_block(head_hits)
        if p.invuln:
            p.invuln -= 1
        if p.y > SH:                       # fell into a pit
            self.reset()
            return

        self.cam = int(max(0, min(p.x + p.w / 2 - SW / 2, LEVEL_W * T - SW)))
        self.level.bumps = {k: v - 1 for k, v in self.level.bumps.items() if v > 1}

        for e in self.enemies:
            if not e.active and e.x < self.cam + SW + T:
                e.active = True
            if e.active:
                e.update(self.level)
            if e.state == "slide" and not (self.cam - SW < e.x < self.cam + 2 * SW):
                e.remove = True
        self.enemy_collisions()
        self.player_enemy_collisions(any(keys[k] for k in JUMP_KEYS))
        self.enemies = [e for e in self.enemies if not e.remove]

        for it in self.items:
            it.update(self.level)
            if not it.rise and p.rect.colliderect(it.rect):
                p.grow()
                self.add_score(1000, it.x, it.y - 20)
                it.remove = True
        self.items = [it for it in self.items if not it.remove]

        for coin in self.coins:
            coin[1] += coin[2]
            coin[2] += 1
            coin[3] -= 1
        self.coins = [coin for coin in self.coins if coin[3] > 0]
        for d in self.debris:
            d[0] += d[2]
            d[1] += d[3]
            d[3] += 0.8
        self.debris = [d for d in self.debris if d[1] < SH]

        if p.x + p.w > CHECK_X - 6:
            self.finished = True

    def enemy_collisions(self):
        live = [e for e in self.enemies if e.active and e.state in ("walk", "shell", "slide")]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if a.state == "dead" or b.state == "dead" or not a.hitbox.colliderect(b.hitbox):
                    continue
                if a.state == "slide" and b.state == "slide":
                    for s in (a, b):
                        s.knock(-1 if s.vx > 0 else 1)
                        self.add_score(500, s.x, s.y - 20)
                elif "slide" in (a.state, b.state):
                    s, v = (a, b) if a.state == "slide" else (b, a)
                    v.knock(1 if s.vx > 0 else -1)
                    self.add_score(SHELL_PTS[min(s.chain, len(SHELL_PTS) - 1)], v.x, v.y - 20)
                    s.chain += 1
                else:   # walkers turn away from each other
                    if a.state == "walk":
                        a.vx = -ENEMY_SPEED if a.x < b.x else ENEMY_SPEED
                    if b.state == "walk":
                        b.vx = -ENEMY_SPEED if b.x < a.x else ENEMY_SPEED

    def player_enemy_collisions(self, jump_held):
        p = self.player
        for e in self.enemies:
            hb = e.hitbox
            if not e.active or e.state in ("dead", "flat") or not p.rect.colliderect(hb):
                continue
            if p.prev_bottom <= hb.top + 12:  # landed on top
                p.y = e.y - p.h
                p.vy = -(JUMP_V if jump_held else STOMP_BOUNCE)
                if e.state == "walk":
                    if e.kind == "g":
                        e.flatten()
                    else:
                        e.set_shell()
                    self.stomp_score(e)
                elif e.state == "shell":
                    self.kick(e)
                else:  # stop a sliding shell
                    e.state, e.vx = "shell", 0
                    self.stomp_score(e)
            elif e.state == "shell":
                self.kick(e)
            elif not (e.state == "slide" and e.grace):
                self.hurt()
                if self.dying:
                    return

    # --- drawing ---
    def draw_tile(self, t, x, y, c, r):
        s = self.screen
        rect = pygame.Rect(x, y, T, T)
        if t == "#":
            pygame.draw.rect(s, GROUND, rect)
            pygame.draw.rect(s, GROUND_DARK, rect, 2)
            pygame.draw.line(s, GROUND_DARK, (x + 8, y + 14), (x + 20, y + 14), 6)
            pygame.draw.line(s, GROUND_DARK, (x + 26, y + 32), (x + 40, y + 32), 6)
        elif t in "BN":
            pygame.draw.rect(s, BRICK, rect)
            for yy in (y, y + T // 2):
                pygame.draw.line(s, MORTAR, (x, yy), (x + T, yy), 3)
            pygame.draw.line(s, MORTAR, (x + T // 2, y), (x + T // 2, y + T // 2), 3)
            for xx in (x + T // 4, x + 3 * T // 4):
                pygame.draw.line(s, MORTAR, (xx, y + T // 2), (xx, y + T), 3)
        elif t in "?MU":
            pygame.draw.rect(s, QBLOCK if t != "U" else USED, rect)
            pygame.draw.rect(s, QDARK, rect, 3)
            for rx, ry in ((5, 5), (T - 9, 5), (5, T - 9), (T - 9, T - 9)):
                pygame.draw.rect(s, QDARK, (x + rx, y + ry, 4, 4))
            if t != "U":
                s.blit(self.qmark, self.qmark.get_rect(center=rect.center))
        elif t == "S":
            pygame.draw.rect(s, STAIR, rect)
            pygame.draw.rect(s, STAIR_LIGHT, (x, y, T, 5))
            pygame.draw.rect(s, STAIR_LIGHT, (x, y, 5, T))
            pygame.draw.rect(s, MORTAR, rect, 2)
        elif t == "p":
            left = self.level.tile(c - 1, r) != "p"
            top = self.level.tile(c, r - 1) != "p"
            body = pygame.Rect(x + 6, y, T - 6, T) if left else pygame.Rect(x, y, T - 6, T)
            pygame.draw.rect(s, PIPE, body)
            if left:
                pygame.draw.rect(s, PIPE_LIGHT, (x + 16, y, 6, T))
            pygame.draw.line(s, PIPE_DARK, (body.left if left else body.right - 1, y),
                             (body.left if left else body.right - 1, y + T), 3)
            if top:
                lip = pygame.Rect(x, y, T, 22)
                pygame.draw.rect(s, PIPE, lip)
                if left:
                    pygame.draw.rect(s, PIPE_LIGHT, (x + 10, y + 2, 6, 18))
                pygame.draw.rect(s, PIPE_DARK, lip, 3)

    def enemy_surface(self, e):
        w, h = e.w, e.h
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        face = 1 if e.vx > 0 else -1
        step = (self.frame // 8) % 2
        if e.kind == "g":
            if e.state == "flat":
                pygame.draw.ellipse(surf, BEETLE, (0, 0, w, h))
                pygame.draw.line(surf, BLACK, (10, h // 2), (w - 10, h // 2), 3)
            else:
                pygame.draw.ellipse(surf, BLACK, (2 + step * 4, h - 10, 16, 10))
                pygame.draw.ellipse(surf, BLACK, (w - 18 - step * 4, h - 10, 16, 10))
                pygame.draw.ellipse(surf, BEETLE, (0, 2, w, h - 8))
                for ex in (w // 2 - 9, w // 2 + 9):
                    pygame.draw.circle(surf, WHITE, (ex + face * 2, 16), 6)
                    pygame.draw.circle(surf, BLACK, (ex + face * 4, 17), 3)
        elif e.state == "walk":
            pygame.draw.ellipse(surf, LIZARD, (6 + step * 4, h - 12, 14, 12))
            pygame.draw.ellipse(surf, LIZARD, (w - 20 - step * 4, h - 12, 14, 12))
            hx = w // 2 + face * 11
            pygame.draw.circle(surf, LIZARD, (hx, 12), 11)
            pygame.draw.circle(surf, BLACK, (hx + face * 5, 9), 3)
            pygame.draw.ellipse(surf, ARMOR, (2, 20, w - 4, h - 28))
            pygame.draw.rect(surf, ARMOR_RIM, (2, h - 18, w - 4, 6))
        else:
            pygame.draw.ellipse(surf, ARMOR, (0, 4, w, h - 4))
            pygame.draw.rect(surf, ARMOR_RIM, (0, h - 14, w, 7))
            for xx in (w // 3, 2 * w // 3):
                pygame.draw.line(surf, ARMOR_RIM, (xx, 8), (xx, h - 14), 2)
        if e.state == "dead":
            surf = pygame.transform.flip(surf, False, True)
        return surf

    def draw_player(self):
        p = self.player
        if p.invuln and (self.frame // 3) % 2:
            return
        s = self.screen
        x, y, w, h, f = int(p.x) - self.cam, int(p.y), p.w, p.h, p.facing
        head = 26 if p.big else 20
        moving = p.on_ground and abs(p.vx) > 0.5
        step = (self.frame // 5) % 2
        for lx, up in ((x + 4, moving and step), (x + w - 16, moving and not step)):
            ly = y + h - 12 - (3 if up else 0)
            pygame.draw.rect(s, PANTS, (lx, ly, 12, 12))
            pygame.draw.rect(s, BOOT, (lx - 1, ly + 7, 14, 5))
        pygame.draw.rect(s, SHIRT, (x + 2, y + head, w - 4, h - head - 10), border_radius=5)
        pygame.draw.rect(s, PANTS, (x + 2, y + h - 18, w - 4, 8))
        pygame.draw.rect(s, SKIN, (x + 5, y + 4, w - 10, head), border_radius=6)
        pygame.draw.rect(s, HAT, (x + 3, y, w - 6, 9), border_radius=4)
        pygame.draw.rect(s, HAT, (x + w - 12 if f > 0 else x - 4, y + 5, 16, 5))
        pygame.draw.rect(s, BLACK, (x + w // 2 + f * 6 - 2, y + 11, 4, 6))

    def text(self, msg, font, x, y, center=False):
        for dx, color in ((2, BLACK), (0, WHITE)):
            img = font.render(msg, True, color)
            pos = img.get_rect(center=(x + dx, y + dx)) if center else (x + dx, y + dx)
            self.screen.blit(img, pos)

    def draw(self):
        s, cam = self.screen, self.cam
        s.fill(SKY)
        for i in range(4, LEVEL_W, 13):             # clouds
            cx, cy = i * T - cam, 70 + (i % 3) * 35
            if -200 < cx < SW + 200:
                for dx, r in ((0, 26), (30, 34), (62, 26)):
                    pygame.draw.circle(s, WHITE, (cx + dx, cy), r)

        for it in self.items:                        # drawn under blocks while rising
            x, y = int(it.x) - cam, int(it.y)
            pygame.draw.ellipse(s, GOLD, (x, y + 8, 36, 28))
            pygame.draw.rect(s, BOOT, (x + 2, y + 4, 32, 12), border_radius=6)
            pygame.draw.rect(s, BOOT, (x + 16, y, 4, 6))
            for ex in (x + 12, x + 24):
                pygame.draw.rect(s, BLACK, (ex - 2, y + 20, 4, 7))

        c0 = cam // T
        offs = [0, 3, 7, 10, 12, 10, 7, 3, 0]
        for r in range(ROWS):
            for c in range(c0, min(c0 + COLS_VIEW + 1, LEVEL_W)):
                t = self.level.grid[r][c]
                if t != " ":
                    dy = offs[self.level.bumps.get((c, r), 0)]
                    self.draw_tile(t, c * T - cam, r * T - dy, c, r)

        px = CHECK_X - cam                           # checkpoint post
        pygame.draw.rect(s, (90, 90, 100), (px - 3, 5 * T, 6, 7 * T))
        pygame.draw.circle(s, GOLD, (px, 5 * T - 10), 14)
        pygame.draw.circle(s, GOLD_DARK, (px, 5 * T - 10), 14, 3)
        pygame.draw.rect(s, (60, 60, 70), (px - 15, 12 * T - 10, 30, 10))

        for x, y, _, _ in self.coins:
            cw = int(abs(math.cos(self.frame * 0.35)) * 20) + 4
            pygame.draw.ellipse(s, GOLD, (x - cam - cw // 2, y, cw, 32))
            pygame.draw.ellipse(s, GOLD_DARK, (x - cam - cw // 2, y, cw, 32), 2)
        for e in self.enemies:
            if -T < e.x - cam < SW + T:
                s.blit(self.enemy_surface(e), (int(e.x) - cam, int(e.y)))
        self.draw_player()
        for x, y, _, _ in self.debris:
            pygame.draw.rect(s, BRICK, (int(x) - cam, int(y), 18, 18))
            pygame.draw.rect(s, MORTAR, (int(x) - cam, int(y), 18, 18), 2)
        for x, y, msg, _ in self.popups:
            self.text(msg, self.small, int(x) - cam, int(y))

        self.text(f"SCORE {self.score:06d}", self.font, 16, 12)
        if self.finished:
            shade = pygame.Surface((SW, SH), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            s.blit(shade, (0, 0))
            self.text("End of demo", self.big_font, SW // 2, SH // 2 - 50, center=True)
            self.text(f"Score: {self.score}", self.font, SW // 2, SH // 2 + 5, center=True)
            self.text("Press R to restart", self.font, SW // 2, SH // 2 + 50, center=True)

    def run(self):
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return
                    if ev.key == pygame.K_r:
                        self.reset()
                    elif ev.key in JUMP_KEYS and not self.finished and not self.dying:
                        self.player.jump()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
    pygame.quit()
    sys.exit()
