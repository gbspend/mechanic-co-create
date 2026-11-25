"""Rule grammar: parsing RULES.txt and the trigger/effect vocabulary.

A rule is   TRIGGER [& TRIGGER ...] -> EFFECT [, EFFECT ...]
  - All triggers must be true (in the same frame) for the effects to run.
  - Prefix a trigger with ! to negate it.
  - Rules run top to bottom, once per frame, before physics moves the entity.

Variables (lowercase names) stand for other entities:
  - A binding trigger such as COLLIDE(e) fills in e, once for every entity it
    finds. Later triggers in the rule filter those matches, and the effects
    run once per surviving match.
  - v(TRIGGER) / v(EFFECT) asks or applies something on entity v instead of self:
        COLLIDE(e) & IS(e, player) & e(FALLING) -> DIE, e(SET_YVEL(8))
  - `self` is always bound to the entity running the rule.
  - A variable must be bound (left to right) before it is used. Binding a
    variable that is already bound filters instead: COLLIDE(e) then means
    "touching e".

To add vocabulary, write a function below with @trigger("NAME") or
@effect("NAME"). It receives (ent, ctx, *args) where args come from the rule
text (numbers become floats, anything else stays a string). Annotate a
parameter to give it a meaning that is checked on load:
    "bind"    a variable this trigger fills in; the function receives None
              there and returns the list of candidate entities
    "ref"     an already-bound variable; the function receives the entity
    "type"    an entity type: a [section] name, or an engine type like _tile
    "spawn"   an entity type that can be spawned (not an engine type like _tile)
    "button"  a BIND name or a key name
    "dir"     LEFT, RIGHT, -1 or 1
Arity is checked too, so typos fail at startup with a line number.

Y velocity in rules is UP-POSITIVE (jump = ADD_YVEL(10), gravity = ADD_YVEL(-0.6)),
even though pygame's screen y grows downward. The conversion happens here.
"""
import inspect
import re
from dataclasses import dataclass, field

import pygame

TRIGGERS = {}
EFFECTS = {}
STOMP_TOLERANCE = 6       # px: how far below a hitbox top a FROM_ABOVE still counts


class RuleError(Exception):
    pass


@dataclass
class Spec:
    fn: object
    kinds: list           # annotation ("bind", "ref", ...) or None, per rule-text parameter
    binds: int = None     # index of the "bind" parameter, if any


def _register(registry, name):
    def deco(fn):
        params = list(inspect.signature(fn).parameters.values())[2:]
        kinds = [p.annotation if isinstance(p.annotation, str) else None for p in params]
        binds = kinds.index("bind") if "bind" in kinds else None
        registry[name] = Spec(fn, kinds, binds)
        return fn
    return deco


def trigger(name):
    return _register(TRIGGERS, name)


def effect(name):
    return _register(EFFECTS, name)


# ---------------------------------------------------------------- input
def key_code(name):
    try:
        return pygame.key.key_code(name.lower())
    except ValueError:
        return None


class Input:
    """Per-frame button state, with named buttons from BIND lines."""

    def __init__(self, bindings):
        self.bindings = bindings          # name -> set of key codes
        self.held = None
        self.pressed = set()
        self.released = set()

    def keys_for(self, button):
        if button in self.bindings:
            return self.bindings[button]
        code = key_code(button)
        return {code} if code is not None else set()

    def is_held(self, b):
        return any(self.held[k] for k in self.keys_for(b))

    def was_pressed(self, b):
        return not self.pressed.isdisjoint(self.keys_for(b))

    def was_released(self, b):
        return not self.released.isdisjoint(self.keys_for(b))


# ---------------------------------------------------------------- triggers
@trigger("AUTO")
def t_auto(ent, ctx):
    return True


@trigger("BUTTON_PRESS")
def t_button_press(ent, ctx, b: "button"):
    return ctx.input.was_pressed(b)


@trigger("BUTTON_HELD")
def t_button_held(ent, ctx, b: "button"):
    return ctx.input.is_held(b)


@trigger("BUTTON_RELEASE")
def t_button_release(ent, ctx, b: "button"):
    return ctx.input.was_released(b)


@trigger("ON_GROUND")
def t_on_ground(ent, ctx):
    return ent.on_ground


@trigger("IN_AIR")
def t_in_air(ent, ctx):
    return not ent.on_ground


@trigger("RISING")
def t_rising(ent, ctx):
    return ent.vy < 0


@trigger("FALLING")
def t_falling(ent, ctx):
    return ent.vy > 0


@trigger("READY")
def t_ready(ent, ctx, timer):
    return ent.timers.get(timer, 0) <= 0


@trigger("START")
def t_start(ent, ctx):
    return ent.age == 0


@trigger("EVERY")
def t_every(ent, ctx, frames):
    return ent.age % max(1, int(frames)) == 0


def _ahead_x(ent):
    return ent.rect.right if ent.facing > 0 else ent.rect.left - 1


@trigger("WALL_AHEAD")
def t_wall_ahead(ent, ctx):
    return ctx.solid_at(_ahead_x(ent), ent.rect.centery)


@trigger("LEDGE_AHEAD")
def t_ledge_ahead(ent, ctx):
    return ent.on_ground and not ctx.solid_at(_ahead_x(ent), ent.rect.bottom + 2)


@trigger("FELL_OUT")
def t_fell_out(ent, ctx):
    return ent.rect.top > ctx.level_h


@trigger("AFTER")
def t_after(ent, ctx, frames):
    return ent.age >= frames


# --- triggers about other entities
@trigger("COLLIDE")
def t_collide(ent, ctx, e: "bind"):
    return [o for o in ent.contacts if not o.dead]


@trigger("NEAR")
def t_near(ent, ctx, e: "bind", dist):
    ax, ay = ent.rect.center
    return [o for o in ctx.entities()
            if o is not ent and not o.dead
            and (o.rect.centerx - ax) ** 2 + (o.rect.centery - ay) ** 2 <= dist * dist]


@trigger("OWNER")
def t_owner(ent, ctx, o: "bind"):
    return [ent.owner] if ent.owner is not None else []


@trigger("IS")
def t_is(ent, ctx, e: "ref", kind: "type"):
    return e.kind == kind


@trigger("FROM_ABOVE")
def t_from_above(ent, ctx, e: "ref"):
    """e's feet were above my hitbox top last frame (i.e. e landed on me)."""
    return e.prev_bottom <= ent.hitbox.top + STOMP_TOLERANCE


@trigger("FROM_BELOW")
def t_from_below(ent, ctx, e: "ref"):
    """e's head was below my hitbox bottom last frame (i.e. e hit me from underneath)."""
    return e.prev_top >= ent.hitbox.bottom - STOMP_TOLERANCE


# ---------------------------------------------------------------- effects
@effect("ADD_XVEL")
def e_add_xvel(ent, ctx, n):
    ent.vx += n


@effect("SET_XVEL")
def e_set_xvel(ent, ctx, n):
    ent.vx = n


@effect("SCALE_XVEL")
def e_scale_xvel(ent, ctx, f):
    ent.vx *= f


@effect("CLAMP_XVEL")
def e_clamp_xvel(ent, ctx, lo, hi):
    ent.vx = max(lo, min(hi, ent.vx))


@effect("ADD_YVEL")
def e_add_yvel(ent, ctx, n):
    ent.vy -= n


@effect("SET_YVEL")
def e_set_yvel(ent, ctx, n):
    ent.vy = -n


@effect("SCALE_YVEL")
def e_scale_yvel(ent, ctx, f):
    ent.vy *= f


@effect("CLAMP_YVEL")
def e_clamp_yvel(ent, ctx, lo, hi):
    ent.vy = -max(lo, min(hi, -ent.vy))


@effect("FACE")
def e_face(ent, ctx, direction: "dir"):
    ent.facing = {"LEFT": -1, "RIGHT": 1}.get(direction) or int(direction)


@effect("FACE_TOWARD")
def e_face_toward(ent, ctx, e: "ref"):
    ent.facing = 1 if e.rect.centerx >= ent.rect.centerx else -1


@effect("TURN")
def e_turn(ent, ctx):
    ent.facing = -ent.facing


@effect("WALK")
def e_walk(ent, ctx, speed):
    ent.vx = ent.facing * speed


@effect("SPRING_Y")
def e_spring_y(ent, ctx, k):
    ent.vy -= k * (ent.fy - ent.home[1])


@effect("DIE")
def e_die(ent, ctx):
    ent.dead = True


@effect("SPAWN")
def e_spawn(ent, ctx, kind: "spawn", owner: "ref" = None):
    """New entity of `kind` just in front of ent, same facing. owner defaults to ent."""
    ctx.spawn(kind, ent, owner if owner is not None else ent)


@effect("COOLDOWN")
def e_cooldown(ent, ctx, timer, frames):
    ent.timers[timer] = frames


# ---------------------------------------------------------------- rules
@dataclass
class Var:
    name: str


@dataclass
class Call:
    name: str
    spec: Spec
    args: tuple
    negate: bool = False
    target: str = None        # variable name for v(...), else None = self

    def resolve(self, env):
        """Args for the function: variables become entities; the bind slot is None."""
        out = []
        for i, a in enumerate(self.args):
            if i == self.spec.binds:
                out.append(None)
            elif isinstance(a, Var):
                out.append(env[a.name])
            else:
                out.append(a)
        return out

    def apply(self, env, ctx):
        self.spec.fn(env[self.target or "self"], ctx, *self.resolve(env))


@dataclass
class Rule:
    triggers: list
    effects: list
    text: str
    line: int

    def matches(self, ent, ctx):
        """Every variable binding that satisfies all triggers."""
        out = []

        def solve(i, env):
            if i == len(self.triggers):
                out.append(dict(env))
                return
            t = self.triggers[i]
            subject = env[t.target or "self"]
            result = t.spec.fn(subject, ctx, *t.resolve(env))
            if t.spec.binds is None:
                if bool(result) != t.negate:
                    solve(i + 1, env)
                return
            var = t.args[t.spec.binds].name
            if var in env:                       # already bound: acts as a filter
                if (env[var] in result) != t.negate:
                    solve(i + 1, env)
            else:
                for cand in result:
                    env[var] = cand
                    solve(i + 1, env)
                env.pop(var, None)

        solve(0, {"self": ent})
        return out

    def run(self, ent, ctx):
        for env in self.matches(ent, ctx):
            if ent.dead:
                break
            for e in self.effects:
                e.apply(env, ctx)


@dataclass
class RuleSet:
    bindings: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)   # section name (entity type) -> [Rule]

    def run(self, section, ent, ctx):
        for rule in self.sections.get(section, ()):
            if ent.dead:          # once DIE runs, the rest of the list is skipped
                break
            rule.run(ent, ctx)


# ---------------------------------------------------------------- parsing
CALL_RE = re.compile(r"^(!?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?$")
VAR_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def split_top(s, sep):
    """Split on sep, ignoring separators inside parentheses."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def parse_arg(a):
    try:
        return float(a)
    except ValueError:
        return a


class Parser:
    def __init__(self, lineno, checks):
        self.lineno = lineno
        self.checks = checks      # deferred (kind, value, lineno) checks: types, buttons

    def err(self, msg):
        raise RuleError(f"line {self.lineno}: {msg}")

    def call(self, text, registry, kind, bound, allow_negate):
        m = CALL_RE.match(text)
        if not m:
            self.err(f"can't parse {kind} {text!r}")
        neg, name, argstr = m.groups()
        if neg and not allow_negate:
            self.err(f"'!' only works on triggers ({text!r})")

        # v(...) : run the inner trigger/effect on entity v
        if VAR_RE.match(name):
            if argstr is None:
                self.err(f"{name!r} is not a {kind}; to use a variable write {name}(SOMETHING)")
            if name not in bound:
                self.err(f"variable {name!r} is used before anything binds it (e.g. COLLIDE({name}))")
            inner = self.call(argstr.strip(), registry, kind, bound, False)
            if inner.target:
                self.err(f"nested variables aren't supported ({text!r})")
            inner.target, inner.negate = name, bool(neg)
            return inner

        if name not in registry:
            known = ", ".join(sorted(registry))
            self.err(f"unknown {kind} {name!r}. Known: {known}")
        spec = registry[name]
        args = [parse_arg(a) for a in split_top(argstr, ",")] if argstr and argstr.strip() else []
        try:
            inspect.signature(spec.fn).bind(None, None, *args)
        except TypeError:
            params = list(inspect.signature(spec.fn).parameters)[2:]
            self.err(f"{name} takes ({', '.join(params)}), got {len(args)} arg(s)")

        for i, a in enumerate(args):
            k = spec.kinds[i] if i < len(spec.kinds) else None
            if k in ("bind", "ref"):
                if not (isinstance(a, str) and VAR_RE.match(a)):
                    self.err(f"{name}: argument {i + 1} must be a lowercase variable name, got {a!r}")
                if k == "ref" and a not in bound:
                    self.err(f"variable {a!r} is used before anything binds it (e.g. COLLIDE({a}))")
                if k == "bind" and a not in bound:
                    if neg:
                        self.err(f"can't bind {a!r} inside a negated trigger ({text!r})")
                    bound.add(a)
                args[i] = Var(a)
            elif k == "dir" and a not in ("LEFT", "RIGHT", -1, 1):
                self.err(f"{name} expects LEFT, RIGHT, -1 or 1, got {a!r}")
            elif k in ("type", "spawn", "button"):
                self.checks.append((k, a, self.lineno))
        return Call(name, spec, tuple(args), bool(neg))


def load_rules(path, engine_types=()):
    """Parse a rules file. engine_types: entity types the game defines itself (e.g. _tile)."""
    rs = RuleSet()
    section = None
    checks = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                rs.sections.setdefault(section, [])
                continue
            if line.upper().startswith("BIND "):
                name, sep, keys = line[5:].partition(":")
                if not sep or not keys.split():
                    raise RuleError(f"line {lineno}: BIND needs 'BIND name: KEY KEY ...'")
                codes = set()
                for k in keys.split():
                    code = key_code(k)
                    if code is None:
                        raise RuleError(f"line {lineno}: unknown key {k!r}")
                    codes.add(code)
                rs.bindings[name.strip()] = codes
                continue
            if "->" not in line:
                raise RuleError(f"line {lineno}: expected 'TRIGGER -> EFFECT', got {line!r}")
            if section is None:
                raise RuleError(f"line {lineno}: rule outside of a [section] such as [player]")
            lhs, rhs = line.split("->", 1)
            p = Parser(lineno, checks)
            bound = {"self"}
            trigs = [p.call(t, TRIGGERS, "trigger", bound, True) for t in split_top(lhs, "&")]
            effs = [p.call(e, EFFECTS, "effect", bound, False) for e in split_top(rhs, ",")]
            rs.sections[section].append(Rule(trigs, effs, line, lineno))

    types = set(rs.sections) | set(engine_types)
    for kind, value, lineno in checks:
        if kind in ("type", "spawn") and value not in types:
            raise RuleError(f"line {lineno}: unknown entity type {value!r}. Known: {', '.join(sorted(types))}")
        if kind == "spawn" and value.startswith("_"):
            raise RuleError(f"line {lineno}: can't SPAWN engine type {value!r}")
        if kind == "button" and not (isinstance(value, str) and (value in rs.bindings or key_code(value))):
            raise RuleError(f"line {lineno}: {value!r} is not a BIND name or key name")
    return rs
