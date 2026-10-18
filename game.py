# =======================================================
# WILDBOUND - animated matplotlib game window
#
#   python game.py
#
# The game rules live in agents.py / model.py and are NOT
# touched here.  This file only DRAWS the game.
#
# How the animation works
#   - Every action is run exactly as before.
#   - Before it we take a snapshot (positions, HP, berries ...),
#     after it we compare, and the differences become
#     animations (lunges, hit flashes, damage numbers, the
#     capture ball, berry bursts ...).
#   - A 25 fps timer glides every sprite towards where the
#     game says it is.
# =======================================================

import contextlib
import io
import math
import random
import re
import sys
import textwrap
import time

# Windows consoles can choke on non-ASCII prints
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Rectangle

# We handle the keys ourselves: switch off matplotlib's shortcuts
# (otherwise "s" opens a save dialog, "q" closes the window ...)
for _key in list(plt.rcParams):
    if _key.startswith("keymap."):
        plt.rcParams[_key] = []

plt.rcParams["toolbar"] = "None"

from config import MAX_ENERGY, NUM_CREATURES
from model import WildboundModel
from pathfinding import path_cost


# =======================================================
# LOOK & FEEL SETTINGS  (visual only)
# =======================================================

FRAME_MS = 40            # 40 ms = 25 frames per second
WALK_MS = 190            # pause between tiles of an automatic A* walk
GLIDE_RATE = 15.0        # how fast sprites slide to their tile
BATTLE_LOCK = 0.15       # extra pause after a battle animation

SPECIES_COLORS = {
    "Sparkit": "#f5c518",
    "Flameling": "#ff6a3d",
    "Aquaff": "#3fb4f5",
    "Leaflet": "#3fa34d",
    "Breezle": "#a98be0",
}

# Blitting: the static map is drawn once, each frame only the moving
# pieces are redrawn.  (Tests switch it off so savefig shows everything.)
BLIT = True

FLOOR = "#f3ecd8"
OUTLINE = [pe.withStroke(linewidth=3, foreground="white")]

MOVE_KEYS = {
    "up": "up", "w": "up",
    "down": "down", "s": "down",
    "left": "left", "a": "left",
    "right": "right", "d": "right",
}


def clean(text):
    """Keep log lines plain ASCII so every font can draw them."""

    return re.sub(r"[^\x20-\x7e]+", "", text).strip()


def blend(color, other, amount):
    """Mix two colours: amount 0 -> color, 1 -> other."""

    a = np.array(to_rgb(color))
    b = np.array(to_rgb(other))

    return tuple(a + (b - a) * max(0.0, min(1.0, amount)))


def flag_moving(*artists):
    """Flag artists as 'moving' so they are drawn every frame on top of
    the cached background."""

    for artist in artists:
        if artist is not None:
            artist.set_animated(BLIT)


def tile_center(pos):
    return pos[0] + 0.5, pos[1] + 0.5


# =======================================================
# SMALL UI HELPERS  (key badges, cards - used by the control
# panel and the rules screen so both look consistent)
# =======================================================

ACCENT = "#2a5bd7"
PANEL_BG = "#fbfaf6"
CARD_BG = "#eef1f6"
INK = "#2a2a2a"
MUTED = "#6b6b6b"


def card(ax, x, y, w, h, color=CARD_BG, accent=None, zorder=0.5):
    """A rounded panel background, optionally with a coloured
    accent bar down the left edge."""

    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6",
        facecolor=color, edgecolor="none", zorder=zorder))

    if accent:

        ax.add_patch(FancyBboxPatch(
            (x, y), 1.3, h, boxstyle="round,pad=0,rounding_size=0.65",
            facecolor=accent, edgecolor="none", zorder=zorder + 0.1))


def pill(ax, x, y, text, color=ACCENT, text_color="white", size=8.5):
    """A small rounded label, e.g. 'Turn 4'."""

    w = max(10.0, 2.4 + 1.55 * len(text))

    ax.add_patch(FancyBboxPatch(
        (x, y), w, 3.6, boxstyle="round,pad=0,rounding_size=1.8",
        facecolor=color, edgecolor="none", zorder=5))

    ax.text(x + w / 2, y + 1.8, text, ha="center", va="center",
            fontsize=size, color=text_color, fontweight="bold", zorder=5.2)

    return w


def key_badge(ax, x, y, label, color=ACCENT, size=8.0):
    """A small rounded 'keycap', e.g. [W] or [Space]."""

    w = max(4.2, 1.7 + 1.35 * len(label))

    ax.add_patch(FancyBboxPatch(
        (x, y), w, 3.3, boxstyle="round,pad=0,rounding_size=0.8",
        facecolor="white", edgecolor=color, linewidth=1.3, zorder=5))

    ax.text(x + w / 2, y + 1.65, label, ha="center", va="center",
            fontsize=size, color=color, fontweight="bold",
            family="monospace", zorder=5.2)

    return w


def key_row(ax, x, y, keys, text, color=ACCENT, size=8.5, gap=1.2):
    """One or more key badges followed by a description, e.g.
    [1] Attack."""

    cx = x

    for k in keys:
        cx += key_badge(ax, cx, y - 0.3, k, color=color) + gap

    ax.text(cx + 0.6, y + 1.35, text, fontsize=size, va="center",
            color=INK, zorder=5.2)


# =======================================================
# SPRITES
# =======================================================

class Sprite:
    """
    A round character: shadow + body + label (+ energy bar).
    `x, y` is where it is drawn, `tx, ty` where the game says it
    should be; update() slides one towards the other and adds
    bobbing, lunges, hit-shakes and jumps on top.
    """

    def __init__(self, ax, cx, cy, color, label, radius, fontsize,
                 label_color="black", bar=False, zorder=9):

        self.ax = ax
        self.x = self.tx = cx
        self.y = self.ty = cy

        self.color = color
        self.radius = radius
        self.fontsize = fontsize

        self.scale = 1.0
        self.scale_goal = 1.0
        self.alpha = 1.0

        self.edge = "#222222"
        self.edge_w = 1.2
        self.bob_amp = 0.03
        self.phase = random.uniform(0, 6.28)

        self.lunge_t = None
        self.lunge_dir = (0.0, 0.0)
        self.hit_t = None
        self.jump_t = None

        self.retire_at = None       # clock time when it leaves the stage
        self.sink = False           # "faint" style exit
        self.dead = False

        self.energy = 1.0
        self.energy_goal = 1.0
        self.bar_color = "#2e9e3e"

        self.shadow = Ellipse(
            (cx, cy - 0.3), 0.6, 0.18, facecolor="black",
            edgecolor="none", alpha=0.18, zorder=zorder - 0.5)

        self.body = Circle(
            (cx, cy), radius, facecolor=color, edgecolor=self.edge,
            linewidth=self.edge_w, zorder=zorder)

        self.label = ax.text(
            cx, cy, label, ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color=label_color, zorder=zorder + 1)

        ax.add_patch(self.shadow)
        ax.add_patch(self.body)

        self.bar_bg = self.bar_fg = None

        if bar:

            self.bar_bg = Rectangle(
                (cx, cy), 0.7, 0.07, facecolor="#cccccc",
                edgecolor="none", zorder=zorder)

            self.bar_fg = Rectangle(
                (cx, cy), 0.7, 0.07, facecolor=self.bar_color,
                edgecolor="none", zorder=zorder + 0.2)

            ax.add_patch(self.bar_bg)
            ax.add_patch(self.bar_fg)

        flag_moving(self.shadow, self.body, self.label, self.bar_bg, self.bar_fg)

    # ---- one-shot animations ----------------------------

    def lunge(self, dx, dy):

        n = math.hypot(dx, dy) or 1.0

        self.lunge_dir = (dx / n, dy / n)
        self.lunge_t = 0.0

    def hit(self):
        self.hit_t = 0.0

    def jump(self):
        self.jump_t = 0.0

    def snap(self, x, y):

        self.x = self.tx = x
        self.y = self.ty = y

    def retire(self, at, sink=False):

        if self.retire_at is None:
            self.retire_at = at
            self.sink = sink

    # ---- per frame --------------------------------------

    def update(self, dt, clock, rate=GLIDE_RATE):

        k = 1 - math.exp(-rate * dt)

        self.x += (self.tx - self.x) * k
        self.y += (self.ty - self.y) * k

        if self.retire_at is not None and clock >= self.retire_at:

            self.scale_goal = 0.0

            if self.sink:
                self.ty = self.y - 0.5 * dt * 3

        self.scale += (self.scale_goal - self.scale) * (1 - math.exp(-14 * dt))

        if self.retire_at is not None and clock >= self.retire_at \
                and self.scale < 0.05:
            self.dead = True

        ox = oy = 0.0
        flash = 0.0

        oy += math.sin(clock * 3.2 + self.phase) * self.bob_amp

        if self.lunge_t is not None:

            self.lunge_t += dt
            p = self.lunge_t / 0.30

            if p >= 1:
                self.lunge_t = None
            else:
                s = math.sin(math.pi * p) * 0.42
                ox += self.lunge_dir[0] * s
                oy += self.lunge_dir[1] * s

        if self.hit_t is not None:

            self.hit_t += dt
            p = self.hit_t / 0.40

            if p >= 1:
                self.hit_t = None
            else:
                ox += math.sin(self.hit_t * 75) * 0.075 * (1 - p)
                flash = 1 - p

        if self.jump_t is not None:

            self.jump_t += dt
            p = self.jump_t / 0.40

            if p >= 1:
                self.jump_t = None
            else:
                oy += abs(math.sin(math.pi * p)) * 0.28

        cx, cy = self.x + ox, self.y + oy

        breathe = 1 + 0.03 * math.sin(clock * 4.0 + self.phase)
        s = max(0.001, self.scale)

        self.body.center = (cx, cy)
        self.body.set_radius(self.radius * s * breathe)
        self.body.set_facecolor(blend(self.color, "#ff2a2a", flash * 0.75)
                                if flash else self.color)
        self.body.set_edgecolor(self.edge)
        self.body.set_linewidth(self.edge_w)
        self.body.set_alpha(self.alpha)

        self.label.set_position((cx, cy))
        self.label.set_fontsize(max(1.0, self.fontsize * s))
        self.label.set_alpha(self.alpha if s > 0.25 else 0.0)

        self.shadow.center = (self.x + ox, self.y - 0.30)
        self.shadow.width = 0.62 * s * (1 - 0.35 * min(1, abs(oy) * 3))
        self.shadow.height = 0.18 * s

        if self.bar_bg is not None:

            self.energy += (self.energy_goal - self.energy) * (1 - math.exp(-6 * dt))

            bx, by = cx - 0.35 * s, cy - 0.44 * s

            for r in (self.bar_bg, self.bar_fg):
                r.set_xy((bx, by))
                r.set_height(0.07 * s)
                r.set_alpha(self.alpha if s > 0.3 else 0.0)

            self.bar_bg.set_width(0.7 * s)
            self.bar_fg.set_width(0.7 * s * max(0.0, min(1.0, self.energy)))
            self.bar_fg.set_facecolor(self.bar_color)

    def remove(self):

        for artist in (self.shadow, self.body, self.label,
                       self.bar_bg, self.bar_fg):
            if artist is not None:
                artist.remove()


class BerrySprite:
    """A berry that grows in when it appears and pulses gently."""

    def __init__(self, ax, cx, cy, grow):

        self.x, self.y = cx, cy
        self.scale = 0.0 if grow else 1.0
        self.phase = random.uniform(0, 6.28)

        self.body = Circle((cx, cy), 0.2, facecolor="#d6173b",
                           edgecolor="#6d0018", linewidth=1.2, zorder=8)

        self.shine = Circle((cx - 0.06, cy + 0.07), 0.05,
                            facecolor="white", edgecolor="none",
                            alpha=0.65, zorder=8.1)

        ax.add_patch(self.body)
        ax.add_patch(self.shine)

        flag_moving(self.body, self.shine)

    def update(self, dt, clock):

        self.scale += (1.0 - self.scale) * (1 - math.exp(-9 * dt))

        pulse = 1 + 0.07 * math.sin(clock * 3.0 + self.phase)
        s = max(0.001, self.scale * pulse)

        self.body.set_radius(0.2 * s)
        self.shine.set_radius(0.05 * s)
        self.shine.center = (self.x - 0.06 * s, self.y + 0.07 * s)

    def remove(self):

        self.body.remove()
        self.shine.remove()


# =======================================================
# SHORT-LIVED EFFECTS   (update(dt) -> still alive?)
# =======================================================

class FloatText:

    def __init__(self, ax, x, y, text, color, size=11, life=0.95, rise=0.55):

        self.x, self.y = x, y
        self.life, self.rise, self.age = life, rise, 0.0

        self.artist = ax.text(
            x, y, text, ha="center", va="center", fontsize=size,
            fontweight="bold", color=color, zorder=30,
            path_effects=OUTLINE)

        flag_moving(self.artist)

    def update(self, dt):

        self.age += dt
        p = min(1.0, self.age / self.life)

        self.artist.set_position((self.x, self.y + self.rise * (1 - (1 - p) ** 2)))
        self.artist.set_alpha(1.0 if p < 0.6 else max(0.0, 1 - (p - 0.6) / 0.4))

        return self.age < self.life

    def remove(self):
        self.artist.remove()


class Burst:
    """An expanding, fading ring."""

    def __init__(self, ax, x, y, color, r0=0.1, r1=0.6, life=0.45):

        self.r0, self.r1, self.life, self.age = r0, r1, life, 0.0
        self.color = color

        self.patch = Circle((x, y), r0, facecolor="none", edgecolor=color,
                            linewidth=3, zorder=25)

        ax.add_patch(self.patch)

        flag_moving(self.patch)

    def update(self, dt):

        self.age += dt
        p = min(1.0, self.age / self.life)

        self.patch.set_radius(self.r0 + (self.r1 - self.r0) * p)
        self.patch.set_alpha(1 - p)
        self.patch.set_linewidth(3 * (1 - p) + 0.5)

        return self.age < self.life

    def remove(self):
        self.patch.remove()


class Sparkle:
    """Little stars flying outwards."""

    def __init__(self, ax, x, y, colors, count=10, life=0.8):

        self.x, self.y, self.life, self.age = x, y, life, 0.0

        self.parts = []

        for i in range(count):

            angle = 2 * math.pi * i / count + random.uniform(-0.2, 0.2)
            speed = random.uniform(0.6, 1.2)

            patch = Circle((x, y), 0.05, facecolor=colors[i % len(colors)],
                           edgecolor="none", zorder=26)

            ax.add_patch(patch)
            flag_moving(patch)

            self.parts.append((patch, angle, speed))

    def update(self, dt):

        self.age += dt
        p = min(1.0, self.age / self.life)

        for patch, angle, speed in self.parts:

            r = speed * p
            patch.center = (self.x + math.cos(angle) * r,
                            self.y + math.sin(angle) * r)
            patch.set_radius(0.07 * (1 - p) + 0.01)
            patch.set_alpha(1 - p)

        return self.age < self.life

    def remove(self):

        for patch, _, _ in self.parts:
            patch.remove()


class Ball:
    """The capture ball: flies, lands, wobbles."""

    FLY = 0.30
    WOBBLE = 0.95

    def __init__(self, ax, x0, y0, x1, y1):

        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.age = 0.0

        self.body = Circle((x0, y0), 0.16, facecolor="#e63946",
                           edgecolor="#222222", linewidth=1.8, zorder=22)

        self.dot = Circle((x0, y0), 0.06, facecolor="white",
                          edgecolor="#222222", linewidth=1, zorder=23)

        ax.add_patch(self.body)
        ax.add_patch(self.dot)

        flag_moving(self.body, self.dot)

    def update(self, dt):

        self.age += dt

        if self.age < self.FLY:

            p = self.age / self.FLY

            x = self.x0 + (self.x1 - self.x0) * p
            y = self.y0 + (self.y1 - self.y0) * p + math.sin(math.pi * p) * 0.6

        else:

            w = self.age - self.FLY

            x = self.x1 + math.sin(w * 17) * 0.09 * max(0.0, 1 - w / self.WOBBLE)
            y = self.y1 - 0.05

        self.body.center = (x, y)
        self.dot.center = (x, y)

        return self.age < self.FLY + self.WOBBLE

    def remove(self):

        self.body.remove()
        self.dot.remove()


class Confetti:
    """Falling coloured paper for the win screen."""

    def __init__(self, ax, width, height, count=90, life=5.0):

        self.w, self.h = width, height
        self.life, self.age = life, 0.0

        self.x = np.random.uniform(0, width, count)
        self.y = height + np.random.uniform(0, 4, count)
        self.vy = np.random.uniform(1.4, 3.0, count)
        self.phase = np.random.uniform(0, 6.28, count)

        colors = list(SPECIES_COLORS.values()) + ["#d6173b"]
        face = [colors[i % len(colors)] for i in range(count)]

        self.scatter = ax.scatter(self.x, self.y, s=26, c=face, marker="s",
                                  zorder=40)

        flag_moving(self.scatter)

    def update(self, dt):

        self.age += dt

        self.y -= self.vy * dt
        self.x += np.sin(self.age * 3 + self.phase) * 0.6 * dt

        self.scatter.set_offsets(np.c_[self.x, self.y])

        return self.age < self.life and bool((self.y > -0.5).any())

    def remove(self):
        self.scatter.remove()


# =======================================================
# THE GAME WINDOW
# =======================================================

class Game:

    def __init__(self):

        self.fig = plt.figure(figsize=(12.5, 6.8))

        try:
            self.fig.canvas.manager.set_window_title("Wildbound")
        except Exception:
            pass

        self.ax_map = self.fig.add_axes([0.03, 0.11, 0.55, 0.85])
        self.ax_info = self.fig.add_axes([0.61, 0.03, 0.38, 0.94])

        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("draw_event", self.on_draw)

        self.bg = None            # cached picture of everything static
        self.need_full = True

        self.phase = "intro"      # "intro" -> "playing", or "help" mid-game
        self.ax_overlay = None

        # automatic A* walk (one tile per tick)
        self.timer = self.fig.canvas.new_timer(interval=WALK_MS)
        self.timer.add_callback(self.walk_tick)

        # animation clock (one frame per tick)
        self.anim_timer = self.fig.canvas.new_timer(interval=FRAME_MS)
        self.anim_timer.add_callback(self.tick)
        self.last_t = time.perf_counter()

        self.new_game()
        self.show_overlay("intro")

        self.anim_timer.start()

    # ===================================================
    # STATE
    # ===================================================

    def new_game(self):

        with contextlib.redirect_stdout(io.StringIO()):
            self.model = WildboundModel()

        self.player = self.model.player

        self.log = []
        self.plan = None          # route the player is looking at
        self.walk = []            # tiles left on an automatic walk
        self.timer.stop()

        # animation state
        self.clock = 0.0
        self.later_calls = []     # (time, function)
        self.fx = []              # running effects
        self.sprites = {}         # creature -> Sprite
        self.berry_sprites = {}   # berry -> BerrySprite
        self.ai_lines = {}        # creature -> (route line, star)
        self.disp_hp = {}         # HP as currently drawn (smooth bars)
        self.hp_hold = {}         # creature -> clock time bars may move
        self.retire_delay = {}
        self.ps_hold = None
        self.lock_until = 0.0
        self.win_shown = False
        self.win_text = None
        self.win_age = 0.0
        self._plans = {}
        self.hp_widgets = []

        self.build_scene()

        self.say(f"Catch or defeat all {NUM_CREATURES} wild creatures!")
        self.say("Walk next to one to start a battle.")

        self.draw()

    def say(self, text):

        for line in str(text).splitlines():

            line = clean(line)

            if line and not line.startswith("="):
                self.log.append(line)

        del self.log[:-30]

    @property
    def walking(self):
        return bool(self.walk)

    # ===================================================
    # RULES / HELP OVERLAY
    #
    # Shown once before the first game (so new players know
    # the controls before they touch anything) and again any
    # time the player presses H.  It is a plain one-off draw
    # on its own full-figure axes, separate from the normal
    # blit loop, so it never interferes with the game scene
    # underneath - dismissing it just removes this axes and
    # lets the cached scene show through again.
    # ===================================================

    def show_overlay(self, mode):

        self.phase = mode
        self.stop_walk()

        if self.ax_overlay is not None:
            self.ax_overlay.remove()

        ax = self.fig.add_axes([0, 0, 1, 1], zorder=50)
        self.ax_overlay = ax

        ax.set_xlim(0, 100)
        ax.set_ylim(100, 0)
        ax.axis("off")

        ax.add_patch(Rectangle((0, 0), 100, 100, facecolor="black",
                               alpha=0.55, edgecolor="none", zorder=0))

        card(ax, 14, 6, 72, 88, color=PANEL_BG, zorder=1)

        first_time = mode == "intro"

        title = "WELCOME TO WILDBOUND" if first_time else "RULES & CONTROLS"
        sub = ("Catch or defeat every wild creature to win."
              if first_time else
              "A quick reminder - press any key or click to resume.")

        ax.text(50, 12, title, ha="center", fontsize=19, fontweight="bold",
               color=INK, zorder=2)
        ax.text(50, 17.5, sub, ha="center", fontsize=9.5, color=MUTED,
               zorder=2)

        y = [22.5]

        def section(label, accent):

            ax.add_patch(Rectangle((19, y[0] + 0.1), 1.4, 3.2,
                                   facecolor=accent, edgecolor="none",
                                   zorder=2))
            ax.text(21.6, y[0] + 2.7, label, fontsize=10.5,
                   fontweight="bold", color=accent, zorder=2)
            y[0] += 6.0

        def line(text, size=8.8, dy=3.6, color=INK):
            ax.text(21, y[0], text, fontsize=size, color=color, zorder=2)
            y[0] += dy

        def keys(items, dy=3.6):

            x = 21

            for k, desc in items:
                x += key_badge(ax, x, y[0] - 2.2, k) + 1.4
                ax.text(x, y[0] - 0.6, desc, fontsize=8.6, va="center",
                       color=INK, zorder=2)
                x += 2.6 + 1.55 * len(desc)

            y[0] += dy

        section("GOAL", "#b8860b")
        line("Explore the map, and capture or defeat every wild creature.")
        y[0] += 0.8

        section("MOVE & EXPLORE", ACCENT)
        keys([("W A S D", "or arrow keys - move one tile")])
        keys([("click", "a tile to plan an A* route")])
        keys([("Enter", "or click again - walk the route")])
        line("Tall grass is slow - A* always finds the cheapest path.",
            size=8.1, color=MUTED, dy=3.2)
        keys([("Space", "wait a turn"), ("Esc", "cancel route")])
        y[0] += 0.8

        section("BATTLE", "#b00000")
        line("Walk next to a wild creature to start a fight.")
        keys([("1", "Attack"), ("2", "Capture"), ("3", "Run")])
        keys([("4", "or Tab - switch creature")])
        line("Capture is more likely the lower its HP is.",
            size=8.1, color=MUTED, dy=3.2)
        y[0] += 0.8

        section("ANYTIME", "#2e9e3e")
        keys([("R", "restart"), ("H", "rules"), ("M", "mute")])

        go = "Press any key or click to begin" if first_time \
            else "Press any key or click to resume"

        ax.text(50, 91, go, ha="center", fontsize=10.5, fontweight="bold",
               color="white", zorder=2,
               bbox=dict(boxstyle="round,pad=0.6", facecolor=ACCENT,
                         edgecolor="none"))

        self.fig.canvas.draw()

    def hide_overlay(self):

        if self.ax_overlay is not None:
            self.ax_overlay.remove()
            self.ax_overlay = None

        self.phase = "playing"
        self.need_full = True

        self.fig.canvas.draw()

    def start_game(self):
        self.hide_overlay()

    def close_help(self):
        self.hide_overlay()

    # ===================================================
    # RUNNING A GAME ACTION  (+ animating what changed)
    # ===================================================

    def snapshot(self):

        m, p = self.model, self.player

        wild = m.wild_creatures()

        return dict(
            enc=p.encounter,
            enc_pos=p.encounter.pos if p.encounter else None,
            team=list(p.team),
            hp={c: c.hp for c in list(p.team) + wild},
            berries=set(m.berries()),
            bpos={b: b.pos for b in m.berries()},
            captured=len(p.captured_creatures),
            active=p.active_creature,
            ppos=p.pos,
        )

    def run(self, action, kind=None):
        """
        Run a game action exactly like before; whatever it prints
        goes to the log.  `kind` ("attack", "capture", "run",
        "switch") only tells the animation what to expect.
        """

        snap = self.snapshot()

        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            result = action()

        self.say(buffer.getvalue())

        self.animate_changes(snap, kind)
        self.sync(grow=True)

        return result

    def later(self, delay, fn):
        self.later_calls.append((self.clock + delay, fn))

    # ---------------------------------------------------
    # snapshot difference -> animations
    # ---------------------------------------------------

    def animate_changes(self, snap, kind):

        m, p = self.model, self.player
        ax = self.ax_map
        ps = self.player_sprite

        enc = snap["enc"]
        d = 0.0

        # ---- a wild creature noticed us ----
        if enc is None and p.encounter is not None:
            self.fx_alert(p.encounter)

        # ---- berries that were eaten ----
        for berry in snap["berries"] - set(m.berries()):

            bx, by = tile_center(snap["bpos"][berry])

            self.fx.append(Burst(ax, bx, by, "#d6173b", 0.1, 0.5))
            self.fx.append(FloatText(ax, bx, by + 0.3, "Nom!", "#2e9e3e", 9))

        # ---- battle ----
        if enc is not None:

            es = self.sprites.get(enc)
            ex, ey = tile_center(snap["enc_pos"])

            if kind == "capture":

                success = len(p.captured_creatures) > snap["captured"]

                d = self.fx_capture(enc, snap["enc_pos"], success)

            elif kind == "attack":

                dmg = snap["hp"][enc] - enc.hp

                if dmg > 0 and es is not None:

                    ps.lunge(ex - ps.x, ey - ps.y)

                    hit_at = 0.18
                    self.hp_hold[enc] = self.clock + hit_at

                    self.later(hit_at, lambda es=es, dmg=dmg: self.hit_sprite(
                        es, dmg, "#ffffff", "#d00000"))

                    if enc.hp <= 0:

                        self.retire_delay[enc] = hit_at + 0.30

                        self.later(hit_at + 0.05, lambda es=es: self.fx.append(
                            FloatText(ax, es.x, es.y + 0.5, "KO!", "#d00000", 12)))

                    d = 0.60

            # ---- the wild creature hits back ----
            active = snap["active"]
            lost = snap["hp"].get(active, active.hp) - active.hp

            healed = any(c.hp > snap["hp"].get(c, c.hp) for c in snap["team"])

            captured_now = len(p.captured_creatures) > snap["captured"]
            defeated_now = enc.hp <= 0

            if (kind in ("attack", "capture") and es is not None
                    and not captured_now and not defeated_now
                    and (lost > 0 or healed)):

                self.later(d, lambda es=es: es.lunge(ps.x - es.x, ps.y - es.y))

                hit_at = d + 0.18

                self.hp_hold[active] = self.clock + hit_at

                if lost > 0:
                    self.later(hit_at, lambda a=active, n=lost:
                               self.hit_sprite(ps, n, "#ffffff", "#d00000"))

                d += 0.62

                if healed:

                    # everybody fainted: back to camp, team healed
                    for c in snap["team"]:
                        self.hp_hold[c] = self.clock + d + 0.9

                    self.later(d, lambda: self.fx.append(FloatText(
                        ax, ps.x, ps.y + 0.6, "All fainted!", "#d00000", 11)))

                    self.ps_hold = (self.clock + d + 0.9,
                                    tile_center(snap["ppos"]))

                    d += 0.9

                elif active.hp <= 0:

                    self.later(d, lambda a=active: self.fx.append(FloatText(
                        ax, ps.x, ps.y + 0.6, f"{a.species} fainted!",
                        "#d00000", 10)))

                    self.later(d + 0.35, lambda: self.fx.append(FloatText(
                        ax, ps.x, ps.y + 0.6, f"Go, {p.active_creature.species}!",
                        "#2a5bd7", 10)))

                    d += 0.6

            if kind == "run" and p.encounter is None:

                self.fx.append(FloatText(ax, ps.x, ps.y + 0.6,
                                         "Got away!", "#2a5bd7", 10))

        # ---- switching creature ----
        if kind == "switch" and p.active_creature is not snap["active"]:

            self.fx.append(Burst(ax, ps.x, ps.y, "#2a5bd7", 0.2, 0.7))
            self.fx.append(FloatText(
                ax, ps.x, ps.y + 0.6, f"Go, {p.active_creature.species}!",
                "#2a5bd7", 10))

        if kind in ("attack", "capture"):
            self.lock_until = self.clock + d + BATTLE_LOCK

        # ---- victory ----
        if m.is_won() and not self.win_shown:

            self.win_shown = True
            self.later(max(d, 0.6) + 0.5, self.show_win)

    def hit_sprite(self, sprite, amount, flash, color):

        sprite.hit()

        self.fx.append(FloatText(
            self.ax_map, sprite.x, sprite.y + 0.45, f"-{amount}", color, 13))

    def fx_alert(self, creature):

        s = self.sprites.get(creature)

        if s is None:
            return

        s.jump()
        self.player_sprite.jump()

        self.fx.append(FloatText(
            self.ax_map, s.x, s.y + 0.55, "!", "#d00000", 20,
            life=1.0, rise=0.25))

    def fx_capture(self, creature, pos, success):
        """Ball flies, creature shrinks into it, ball wobbles, result."""

        ax = self.ax_map
        ps = self.player_sprite
        s = self.sprites.get(creature)
        ex, ey = tile_center(pos)

        self.fx.append(Ball(ax, ps.x, ps.y, ex, ey))

        total = Ball.FLY + Ball.WOBBLE + 0.05

        if s is not None:

            def shrink(s=s):
                s.scale_goal = 0.0

            self.later(Ball.FLY, shrink)

        if success:

            self.retire_delay[creature] = Ball.FLY

            def win_fx():

                self.fx.append(Sparkle(ax, ex, ey,
                                       ["#f5c518", "#ffffff", "#ff6a3d"]))
                self.fx.append(Burst(ax, ex, ey, "#f5c518", 0.1, 0.8, 0.6))
                self.fx.append(FloatText(ax, ex, ey + 0.4, "Captured!",
                                         "#b8860b", 12))

            self.later(total, win_fx)

        else:

            def free(s=s):

                if s is not None:
                    s.scale_goal = 1.0
                    s.jump()

                self.fx.append(Burst(ax, ex, ey, "#ffffff", 0.1, 0.7))
                self.fx.append(FloatText(ax, ex, ey + 0.5, "Broke free!",
                                         "#d00000", 11))

            self.later(total, free)

        return total + 0.15

    def show_win(self):

        m, p = self.model, self.player

        W, H = m.grid.width, m.grid.height

        self.win_text = self.ax_map.text(
            W / 2, H / 2,
            f"ALL CLEAR!\nCaught {len(p.captured_creatures)}, "
            f"defeated {p.defeated}\nin {m.step_count} turns\n\n"
            "Press R to play again",
            ha="center", va="center", fontsize=15, fontweight="bold",
            zorder=50, alpha=0.0,
            bbox=dict(boxstyle="round,pad=0.8", facecolor="white",
                      edgecolor="black"))

        flag_moving(self.win_text)

        self.win_age = 0.0

        self.fx.append(Confetti(self.ax_map, W, H))

    # ===================================================
    # MOVING
    # ===================================================

    def move(self, direction):

        def action():

            moved = self.player.move(direction)

            if moved:
                self.model.step()

            return moved

        self.plan = None
        self.run(action)

    def wait(self):

        self.plan = None
        self.run(self.model.step)

    def walk_tick(self):

        if not self.walk or self.player.encounter is not None:
            self.stop_walk()
            self.draw()
            return

        target = self.walk.pop(0)

        def action():

            moved = self.player.step_to(target)

            if moved:
                self.model.step()

            return moved

        if not self.run(action):
            self.walk = []

        if self.player.encounter is not None:
            self.say("Travel interrupted!")
            self.walk = []

        if not self.walk:
            self.stop_walk()

        self.draw()

    def stop_walk(self):

        self.walk = []
        self.timer.stop()

    def start_walk(self):

        if self.plan and len(self.plan) > 1:

            self.walk = list(self.plan[1:])
            self.plan = None
            self.timer.start()

    # ===================================================
    # INPUT
    # ===================================================

    def on_key(self, event):

        key = (event.key or "").lower()

        if self.phase == "intro":
            self.start_game()
            return

        if self.phase == "help":
            self.close_help()
            return

        if key == "r":
            self.new_game()
            return

        if key == "h":
            self.show_overlay("help")
            return

        if self.walking:
            self.stop_walk()          # any key cancels the walk
            self.say("Walk cancelled.")
            self.draw()
            return

        if self.model.is_won():
            return

        p = self.player

        if p.encounter is not None:

            # let the battle animation finish first
            if self.clock < self.lock_until:
                return

            if key == "1":
                self.run(p.attack, "attack")
            elif key == "2":
                self.run(p.attempt_capture, "capture")
            elif key == "3":
                self.run(p.run_away, "run")
            elif key in ("4", "tab"):
                self.run(p.next_creature, "switch")
            else:
                return

        elif key in MOVE_KEYS:
            self.move(MOVE_KEYS[key])

        elif key in (" ", "space"):
            self.wait()

        elif key == "enter":
            self.start_walk()

        elif key == "escape":
            self.plan = None

        elif key in ("4", "tab"):
            self.run(p.next_creature, "switch")

        else:
            return

        self.draw()

    def on_click(self, event):

        if self.phase == "intro":
            self.start_game()
            return

        if self.phase == "help":
            self.close_help()
            return

        if event.inaxes is not self.ax_map or event.xdata is None:
            return

        if self.walking or self.player.encounter is not None:
            return

        if self.model.is_won():
            return

        goal = (int(event.xdata), int(event.ydata))

        # second click on the same tile = go
        if self.plan and self.plan[-1] == goal:
            self.start_walk()
            self.draw()
            return

        path = self.player.plan_path(goal)

        if path is None:
            self.plan = None
            self.say("No route there (rock or walled in).")

        elif len(path) < 2:
            self.plan = None

        else:
            self.plan = path
            cost = path_cost(path, self.model.move_cost)
            self.say(
                f"A* route: {len(path) - 1} steps, cost {cost}. "
                "Click again or press Enter to go."
            )

        self.draw()

    # ===================================================
    # SCENE  (built once per game; moved by advance())
    # ===================================================

    def build_scene(self):

        m = self.model
        ax = self.ax_map

        W, H = m.grid.width, m.grid.height

        ax.clear()
        ax.set_facecolor(FLOOR)
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.set_aspect("equal", adjustable="box")

        for (x, y), kind in m.terrain.items():

            if kind == "rock":

                ax.add_patch(FancyBboxPatch(
                    (x + 0.08, y + 0.08), 0.84, 0.84,
                    boxstyle="round,pad=0,rounding_size=0.15",
                    facecolor="#6f6f6f", edgecolor="#2b2b2b",
                    linewidth=1.2, zorder=1))

            else:

                ax.add_patch(Rectangle(
                    (x, y), 1, 1, facecolor="#a9dd9b",
                    edgecolor="#6fb862", hatch="////",
                    linewidth=0.6, zorder=0.8))

        ax.set_xticks([i + 0.5 for i in range(W)])
        ax.set_xticklabels(range(W), fontsize=8)
        ax.set_yticks([i + 0.5 for i in range(H)])
        ax.set_yticklabels(range(H), fontsize=8)
        ax.tick_params(length=0)

        ax.set_xticks(range(W + 1), minor=True)
        ax.set_yticks(range(H + 1), minor=True)
        ax.grid(which="minor", color="black", alpha=0.15, linewidth=0.7)
        ax.tick_params(which="minor", length=0)

        ax.legend(
            handles=[
                Line2D([0], [0], marker="o", linestyle="None",
                       markerfacecolor="#d6173b", markeredgecolor="#6d0018",
                       markersize=8, label="Berry"),
                Line2D([0], [0], marker="s", linestyle="None",
                       markerfacecolor="#6f6f6f", markeredgecolor="#2b2b2b",
                       markersize=9, label="Rock"),
                Line2D([0], [0], marker="s", linestyle="None",
                       markerfacecolor="#a9dd9b", markeredgecolor="#6fb862",
                       markersize=9, label="Tall grass (slow)"),
                Line2D([0], [0], color="#ff8c00", linestyle="--",
                       label="Hungry creature's A* route"),
                Line2D([0], [0], color="#2a5bd7", label="Your A* route"),
            ],
            loc="upper center", bbox_to_anchor=(0.5, -0.04),
            ncol=3, fontsize=8, frameon=False)

        # your planned route: line + target X + a dot running along it
        self.route_line = Line2D([], [], color="#2a5bd7", linewidth=3.2,
                                 alpha=0.85, marker="o", markersize=4.5,
                                 zorder=5)
        self.route_x = Line2D([], [], color="#2a5bd7", marker="X",
                              linestyle="None", markersize=15, zorder=6)
        self.route_dot = Line2D([], [], color="white", marker="o",
                                markeredgecolor="#2a5bd7", markeredgewidth=2,
                                linestyle="None", markersize=9, zorder=6.5)

        for line in (self.route_line, self.route_x, self.route_dot):
            ax.add_line(line)
            flag_moving(line)

        # the player
        px, py = tile_center(self.player.pos)

        self.player_sprite = Sprite(
            ax, px, py, "black", "YOU", 0.38, 7,
            label_color="white", zorder=12)

        self.player_sprite.edge = "white"
        self.player_sprite.edge_w = 3
        self.player_sprite.bob_amp = 0.02

        self.sync(grow=False)

    # ===================================================
    # SYNC  (called after every game change)
    # ===================================================

    def sync(self, grow=True):
        """Create / retire sprites so they match the game state."""

        m, p = self.model, self.player
        ax = self.ax_map

        wild = m.wild_creatures()

        # ---- creatures ----
        for c in wild:

            if c not in self.sprites:

                cx, cy = tile_center(c.pos)

                s = Sprite(ax, cx, cy, SPECIES_COLORS.get(c.species, "#888888"),
                           c.species[0], 0.34, 11, bar=True, zorder=9)

                s.energy = s.energy_goal = c.energy / MAX_ENERGY

                self.sprites[c] = s

                line = Line2D([], [], color="#ff8c00", linestyle="--",
                              linewidth=2.2, marker="o", markersize=3.5,
                              zorder=5)

                star = Line2D([], [], color="#ff8c00", marker="*",
                              markerfacecolor="none", markeredgewidth=2,
                              linestyle="None", markersize=20, zorder=7)

                ax.add_line(line)
                ax.add_line(star)
                flag_moving(line, star)

                self.ai_lines[c] = (line, star)

        for c, s in self.sprites.items():

            if c not in wild:
                s.retire(self.clock + self.retire_delay.pop(c, 0.0),
                         sink=c.hp <= 0)

        # ---- berries ----
        current = m.berries()

        for b in current:

            if b not in self.berry_sprites:

                bx, by = tile_center(b.pos)
                self.berry_sprites[b] = BerrySprite(ax, bx, by, grow)

        for b in list(self.berry_sprites):

            if b not in current:
                self.berry_sprites.pop(b).remove()

        # ---- A* routes of hungry creatures (same function the AI uses) ----
        self._plans = {}

        for c in wild:

            line, star = self.ai_lines[c]

            plan = c.plan_food_route() if c.is_hungry else None

            if plan:

                path, berry = plan

                self._plans[c] = plan

                line.set_data([q[0] + 0.5 for q in path],
                              [q[1] + 0.5 for q in path])

                star.set_data([berry.pos[0] + 0.5], [berry.pos[1] + 0.5])

            else:

                line.set_data([], [])
                star.set_data([], [])

        # ---- your planned route ----
        if self.plan and len(self.plan) > 1:

            self.route_line.set_data([q[0] + 0.5 for q in self.plan],
                                     [q[1] + 0.5 for q in self.plan])

            self.route_x.set_data([self.plan[-1][0] + 0.5],
                                  [self.plan[-1][1] + 0.5])

        else:

            self.route_line.set_data([], [])
            self.route_x.set_data([], [])
            self.route_dot.set_data([], [])

        self.draw_info()

    def draw(self):

        self.sync(grow=True)

        self.need_full = True       # static parts (info panel ...) changed

        if not BLIT:
            self.fig.canvas.draw_idle()

    def on_draw(self, event):
        """A full redraw just happened: remember it as the background."""

        if BLIT:
            self.bg = self.fig.canvas.copy_from_bbox(self.fig.bbox)

    def render(self):

        if self.phase != "playing":
            return          # the rules overlay is showing; leave it alone

        canvas = self.fig.canvas

        if not BLIT:
            canvas.draw_idle()
            return

        if self.need_full or self.bg is None:
            canvas.draw()                 # on_draw() stores the background
            self.need_full = False

        canvas.restore_region(self.bg)

        for ax in (self.ax_map, self.ax_info):

            moving = [a for a in ax.get_children() if a.get_animated()]

            for artist in sorted(moving, key=lambda a: a.get_zorder()):
                ax.draw_artist(artist)

        canvas.blit(self.fig.bbox)

    # ===================================================
    # ANIMATION CLOCK
    # ===================================================

    def tick(self):

        now = time.perf_counter()
        dt = min(0.1, now - self.last_t)
        self.last_t = now

        self.advance(dt)

        self.render()

    def advance(self, dt):
        """Move the animation forward by dt seconds."""

        p = self.player
        m = self.model

        self.clock += dt
        clock = self.clock

        # delayed calls
        due = [c for c in self.later_calls if c[0] <= clock]

        if due:

            self.later_calls = [c for c in self.later_calls if c[0] > clock]

            for _, fn in sorted(due, key=lambda c: c[0]):
                fn()

        # ---- the player ----
        ps = self.player_sprite

        target = tile_center(p.pos)

        if self.ps_hold is not None:

            until, held = self.ps_hold

            if clock < until:
                target = held

            else:
                self.ps_hold = None
                ps.snap(*target)               # teleport back to camp
                ps.jump()
                self.fx.append(Burst(self.ax_map, *target, "#2a5bd7", 0.2, 0.9))
                self.fx.append(FloatText(self.ax_map, target[0], target[1] + 0.6,
                                         "Healed!", "#2e9e3e", 11))

        ps.tx, ps.ty = target

        ps.edge = "#d00000" if p.encounter else "white"
        ps.edge_w = 3 + (1.2 * math.sin(clock * 9) if p.encounter else 0)

        ps.update(dt, clock, rate=GLIDE_RATE + 4)

        # ---- wild creatures ----
        for c, s in list(self.sprites.items()):

            if c.pos is not None:
                s.tx, s.ty = tile_center(c.pos)

            fighting = p.encounter is c
            hungry = c.is_hungry and c.hp > 0

            if fighting:
                s.edge, s.edge_w = "#d00000", 3 + 1.2 * math.sin(clock * 9)
            elif hungry:
                s.edge, s.edge_w = "#ff8c00", 2.6 + 0.8 * math.sin(clock * 5)
            else:
                s.edge, s.edge_w = "#222222", 1.2

            s.energy_goal = c.energy / MAX_ENERGY
            s.bar_color = "#ff8c00" if hungry else "#2e9e3e"

            s.update(dt, clock)

            if s.dead:

                s.remove()
                del self.sprites[c]

                line, star = self.ai_lines.pop(c)
                line.remove()
                star.remove()

        # ---- berries ----
        for b in self.berry_sprites.values():
            b.update(dt, clock)

        # ---- marching-ants routes ----
        offset = -clock * 12

        for line, _ in self.ai_lines.values():
            line.set_linestyle((offset, (4.5, 3.0)))

        if self.plan and len(self.plan) > 1:

            pts = self.plan
            n = len(pts) - 1
            u = (clock * 5.0) % n
            i = int(u)
            f = u - i

            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f + 0.5
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f + 0.5

            self.route_dot.set_data([x], [y])
            self.route_x.set_markersize(14 + 3 * math.sin(clock * 6))

        # ---- smooth HP bars ----
        for c, disp in list(self.disp_hp.items()):

            if self.hp_hold.get(c, 0.0) > clock:
                continue

            disp += (c.hp - disp) * (1 - math.exp(-9 * dt))

            if abs(disp - c.hp) < 0.3:
                disp = c.hp

            self.disp_hp[c] = disp

        for c, fg, width, txt in self.hp_widgets:

            disp = self.disp_hp.get(c, c.hp)

            fg.set_width(width * max(0.0, disp) / c.max_hp)
            txt.set_text(f"{round(disp):>3}/{c.max_hp}")

        # ---- effects ----
        alive = []

        for fx in self.fx:

            if fx.update(dt):
                alive.append(fx)
            else:
                fx.remove()

        self.fx = alive

        # ---- win banner fade-in ----
        if self.win_text is not None:

            self.win_age += dt
            self.win_text.set_alpha(min(1.0, self.win_age / 0.6))

    # ===================================================
    # INFO PANEL  (rebuilt after every game change)
    # ===================================================

    def draw_info(self):

        m = self.model
        p = self.player
        ax = self.ax_info

        ax.clear()
        ax.set_xlim(0, 100)
        ax.set_ylim(100, 0)
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 100, 100, facecolor=PANEL_BG,
                               edgecolor="none", zorder=0))

        self.hp_widgets = []

        wild = m.wild_creatures()

        # ---- header: title + live stats pills ----
        ax.text(0, 2.2, "WILDBOUND", fontsize=18, fontweight="bold",
               color=INK, zorder=2)
        ax.text(100, 2.2, "[H] rules", ha="right", fontsize=8,
               color=MUTED, zorder=2)

        px = 0.0

        for label, color in (
            (f"Turn {m.step_count}", "#555555"),
            (f"Wild left {len(wild)}", "#b00000" if wild else "#2e9e3e"),
            (f"Caught {len(p.captured_creatures)}", "#b8860b"),
        ):
            px += pill(ax, px, 8.6, label, color=color) + 1.6

        y = [15.5]       # current line (a list so helpers can change it)

        def text(s, x=3, size=9, **kw):

            return ax.text(x, y[0], s, fontsize=size, va="top", **kw)

        def skip(n):
            y[0] += n

        def section_start(height, accent):

            top = y[0] - 1.6
            card(ax, 0, top, 100, height, accent=accent)
            y[0] += 1.8

            return top

        def heading(s, color=INK):

            text(s, size=9.5, fontweight="bold", color=color, x=4.4)
            skip(4.3)

        def hp_row(creature, color):

            disp = self.disp_hp.setdefault(creature, creature.hp)
            frac = max(0.0, disp) / creature.max_hp

            bx, bw, bh = 34, 40, 2.4

            ax.add_patch(FancyBboxPatch(
                (bx, y[0] + 0.3), bw, bh,
                boxstyle="round,pad=0,rounding_size=1.2",
                facecolor="#dddddd", edgecolor="none"))

            fg = FancyBboxPatch(
                (bx, y[0] + 0.3), max(0.6, bw * frac), bh,
                boxstyle="round,pad=0,rounding_size=1.2",
                facecolor=color if creature.hp > 0 else "#888888",
                edgecolor="none")

            ax.add_patch(fg)

            txt = text(f"{round(disp):>3}/{creature.max_hp}", x=77,
                      family="monospace")

            flag_moving(fg, txt)

            self.hp_widgets.append((creature, fg, bw, txt))

        # ---- team card ----
        team_h = 4.0 + 7.6 * len(p.team) + 1.0
        section_start(team_h, ACCENT)

        header_y = y[0]
        heading("YOUR TEAM")
        ax.text(96, header_y, "[4]/[Tab] switch", ha="right", fontsize=7.6,
               color=MUTED, va="top", zorder=2)
        skip(0.3)

        for c in p.team:

            active = c is p.active_creature

            text(("> " if active else "  ") + c.species,
                fontweight="bold" if active else "normal",
                color=ACCENT if active else INK)

            hp_row(c, "#2e9e3e")

            skip(3.4)

        skip(2.0)

        # ---- battle / controls card ----
        if p.encounter is not None:

            e = p.encounter

            bh = 18.5
            section_start(bh, "#b00000")

            heading("BATTLE!", color="#b00000")

            text(f"Wild {e.species}", fontweight="bold", color="#b00000")

            hp_row(e, "#d03030")

            skip(4.2)

            key_row(ax, 4, y[0], ["1"], "Attack", color="#b00000")
            skip(4.2)
            key_row(ax, 4, y[0], ["2"], "Capture", color="#b00000")
            skip(4.2)
            key_row(ax, 4, y[0], ["3"], "Run", color="#b00000")
            skip(4.6)

            text("Capture is likelier at low HP.", size=7.8, color=MUTED)
            skip(3.8)

        elif m.is_won():

            section_start(14.0, "#2e9e3e")

            heading("YOU WIN!", color="#2e9e3e")
            text(f"Caught {len(p.captured_creatures)}, "
                f"defeated {p.defeated}.", size=8.5)
            skip(4.0)
            key_row(ax, 4, y[0], ["R"], "play again")
            skip(4.5)

        else:

            section_start(22.0, ACCENT)

            heading("CONTROLS")

            key_row(ax, 4, y[0], ["W", "A", "S", "D"], "move")
            skip(4.4)
            key_row(ax, 4, y[0], ["click"], "plan A* route")
            skip(4.4)
            key_row(ax, 4, y[0], ["Enter"], "follow it")
            skip(4.4)
            key_row(ax, 4, y[0], ["Space"], "wait")
            skip(4.4)
            key_row(ax, 4, y[0], ["Esc"], "cancel route")
            skip(4.6)

        skip(2.0)

        # ---- AI status card ----
        ai_h = 4.0 + 3.6 * max(1, len(wild)) + 1.0
        section_start(ai_h, "#ff8c00")

        heading("WILD CREATURES (AI)", color="#b85c00")

        for c in wild:

            plan = self._plans.get(c)

            if p.encounter is c:
                state = "fighting you"
            elif plan:
                path, berry = plan
                state = (f"-> berry {berry.pos}, "
                         f"cost {path_cost(path, m.move_cost)}")
            elif c.is_hungry:
                state = "hungry, searching"
            elif c.calm > 0:
                state = "avoiding you"
            else:
                state = "wandering"

            text(f"{c.species:<9} E{c.energy:>3}  {state}", size=7.8,
                family="monospace")

            skip(3.4)

        if not wild:
            text("none left", size=8, color=MUTED)
            skip(3.4)

        skip(2.0)

        # ---- log card: only as many lines as actually fit below
        # everything else, so a big team + a long log can never spill
        # past the bottom of the panel ----
        lines = []

        for entry in self.log[-10:]:
            lines.extend(textwrap.wrap(entry, 50) or [""])

        room = 100 - (y[0] - 1.6) - 2.0 - 5.0
        max_lines = max(1, int(room / 3.2))

        lines = lines[-min(7, max_lines):]

        log_h = 4.0 + 3.2 * max(1, len(lines)) + 1.0
        section_start(log_h, "#8a8a8a")

        heading("LOG")

        for line in lines:

            text(line, size=7.8, color="#444444")
            skip(3.2)


# =======================================================
# START
# =======================================================

if __name__ == "__main__":

    game = Game()

    plt.show()