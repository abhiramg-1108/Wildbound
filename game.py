# =======================================================
# WILDBOUND - matplotlib game window
#
#   python game.py
#
# One window: the map on the left, status / team / AI /
# message log on the right.  Everything is keyboard or
# mouse driven.  No extra libraries needed besides
# mesa and matplotlib.
# =======================================================

import contextlib
import io
import re
import sys
import textwrap

# Windows consoles can choke on non-ASCII prints
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

# We handle the keys ourselves: switch off matplotlib's shortcuts
# (otherwise "s" opens a save dialog, "q" closes the window ...)
for _key in list(plt.rcParams):
    if _key.startswith("keymap."):
        plt.rcParams[_key] = []

plt.rcParams["toolbar"] = "None"

from config import MAX_ENERGY, NUM_CREATURES
from model import WildboundModel
from pathfinding import path_cost


SPECIES_COLORS = {
    "Sparkit": "#f5c518",
    "Flameling": "#ff6a3d",
    "Aquaff": "#3fb4f5",
    "Leaflet": "#3fa34d",
    "Breezle": "#a98be0",
}

FLOOR = "#f3ecd8"
WALK_MS = 170            # speed of the automatic A* walk

MOVE_KEYS = {
    "up": "up", "w": "up",
    "down": "down", "s": "down",
    "left": "left", "a": "left",
    "right": "right", "d": "right",
}


def clean(text):
    """Keep log lines plain ASCII so every font can draw them."""

    return re.sub(r"[^\x20-\x7e]+", "", text).strip()


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

        self.timer = self.fig.canvas.new_timer(interval=WALK_MS)
        self.timer.add_callback(self.walk_tick)

        self.new_game()

    # ---------------------------------------------------
    # state
    # ---------------------------------------------------

    def new_game(self):

        with contextlib.redirect_stdout(io.StringIO()):
            self.model = WildboundModel()

        self.player = self.model.player

        self.log = []
        self.plan = None          # route the player is looking at
        self.walk = []            # tiles left on an automatic walk
        self.timer.stop()

        self.say(f"Catch or defeat all {NUM_CREATURES} wild creatures!")
        self.say("Walk next to one to start a battle.")

        self.draw()

    def say(self, text):

        for line in str(text).splitlines():

            line = clean(line)

            if line and not line.startswith("="):
                self.log.append(line)

        del self.log[:-30]

    def run(self, action):
        """Run a game action; whatever it prints goes to the log."""

        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            result = action()

        self.say(buffer.getvalue())

        return result

    @property
    def walking(self):
        return bool(self.walk)

    # ---------------------------------------------------
    # one player turn = move, then the world reacts
    # ---------------------------------------------------

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

    # ---------------------------------------------------
    # input
    # ---------------------------------------------------

    def on_key(self, event):

        key = (event.key or "").lower()

        if key == "r":
            self.new_game()
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

            if key == "1":
                self.run(p.attack)
            elif key == "2":
                self.run(p.attempt_capture)
            elif key == "3":
                self.run(p.run_away)
            elif key in ("4", "tab"):
                self.run(p.next_creature)
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
            self.run(p.next_creature)

        else:
            return

        self.draw()

    def on_click(self, event):

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
    # DRAWING
    # ===================================================

    def draw(self):

        self.draw_map()
        self.draw_info()
        self.fig.canvas.draw_idle()

    # ---------------------------------------------------
    # map
    # ---------------------------------------------------

    def draw_map(self):

        m = self.model
        p = self.player
        ax = self.ax_map

        W, H = m.grid.width, m.grid.height

        ax.clear()
        ax.set_facecolor(FLOOR)
        ax.set_xlim(0, W)
        ax.set_ylim(0, H)
        ax.set_aspect("equal", adjustable="box")

        # terrain
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

        # wild creatures that are hungry show their A* route
        wild = m.wild_creatures()
        plans = {}

        for c in wild:

            if c.is_hungry:

                plan = c.plan_food_route()

                if plan:

                    plans[c] = plan

                    path, berry = plan

                    ax.plot(
                        [q[0] + 0.5 for q in path],
                        [q[1] + 0.5 for q in path],
                        linestyle="--", linewidth=2.2, color="#ff8c00",
                        marker="o", markersize=3.5, zorder=5)

                    ax.scatter(
                        berry.pos[0] + 0.5, berry.pos[1] + 0.5,
                        s=420, marker="*", facecolors="none",
                        edgecolors="#ff8c00", linewidths=2, zorder=7)

        self._plans = plans

        # the player's own planned route
        if self.plan and len(self.plan) > 1:

            ax.plot(
                [q[0] + 0.5 for q in self.plan],
                [q[1] + 0.5 for q in self.plan],
                color="#2a5bd7", linewidth=3.2, alpha=0.85,
                marker="o", markersize=4.5, zorder=5)

            gx, gy = self.plan[-1]

            ax.scatter(gx + 0.5, gy + 0.5, s=330, marker="X",
                       color="#2a5bd7", zorder=6)

        # berries
        for b in m.berries():

            ax.add_patch(Circle(
                (b.pos[0] + 0.5, b.pos[1] + 0.5), 0.2,
                facecolor="#d6173b", edgecolor="#6d0018",
                linewidth=1.2, zorder=8))

        # wild creatures
        for c in wild:

            cx, cy = c.pos[0] + 0.5, c.pos[1] + 0.5

            fighting = p.encounter is c

            ax.add_patch(Circle(
                (cx, cy), 0.34,
                facecolor=SPECIES_COLORS.get(c.species, "#888888"),
                edgecolor="#d00000" if fighting
                else ("#ff8c00" if c.is_hungry else "#222222"),
                linewidth=3 if (fighting or c.is_hungry) else 1.2,
                zorder=9))

            ax.text(cx, cy, c.species[0], ha="center", va="center",
                    fontsize=11, fontweight="bold", zorder=10)

            # small energy bar under the creature
            frac = c.energy / MAX_ENERGY

            ax.add_patch(Rectangle(
                (c.pos[0] + 0.15, c.pos[1] + 0.06), 0.7, 0.07,
                facecolor="#cccccc", edgecolor="none", zorder=9))

            ax.add_patch(Rectangle(
                (c.pos[0] + 0.15, c.pos[1] + 0.06), 0.7 * frac, 0.07,
                facecolor="#ff8c00" if c.is_hungry else "#2e9e3e",
                edgecolor="none", zorder=9.5))

        # player
        if p.pos is not None:

            px, py = p.pos[0] + 0.5, p.pos[1] + 0.5

            ax.add_patch(Circle(
                (px, py), 0.38, facecolor="black",
                edgecolor="#d00000" if p.encounter else "white",
                linewidth=3, zorder=12))

            ax.text(px, py, "YOU", ha="center", va="center",
                    fontsize=7, fontweight="bold", color="white",
                    zorder=13)

        # axes
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

        if m.is_won():

            ax.text(
                W / 2, H / 2,
                f"ALL CLEAR!\nCaught {len(p.captured_creatures)}, "
                f"defeated {p.defeated}\nin {m.step_count} turns\n\n"
                "Press R to play again",
                ha="center", va="center", fontsize=15, fontweight="bold",
                zorder=20,
                bbox=dict(boxstyle="round,pad=0.8", facecolor="white",
                          edgecolor="black", alpha=0.95))

    # ---------------------------------------------------
    # info panel
    # ---------------------------------------------------

    def draw_info(self):

        m = self.model
        p = self.player
        ax = self.ax_info

        ax.clear()
        ax.set_xlim(0, 100)
        ax.set_ylim(100, 0)
        ax.axis("off")

        y = [2.0]       # current line (a list so helpers can change it)

        def text(s, x=0, size=9, **kw):

            ax.text(x, y[0], s, fontsize=size, va="top",
                    family="monospace", **kw)

        def skip(n):
            y[0] += n

        def heading(s):

            skip(1)
            text(s, size=9.5, fontweight="bold", color="#444444")
            skip(4.2)

        def bar(x, w, frac, color):

            ax.add_patch(Rectangle(
                (x, y[0] + 0.3), w, 2.2,
                facecolor="#dddddd", edgecolor="none"))

            ax.add_patch(Rectangle(
                (x, y[0] + 0.3), w * max(0, min(1, frac)), 2.2,
                facecolor=color, edgecolor="none"))

        # title + status
        text("WILDBOUND", size=18, fontweight="bold")
        skip(8)

        wild = m.wild_creatures()

        text(f"Turn {m.step_count}   Wild left: {len(wild)}   "
             f"Caught: {len(p.captured_creatures)}")
        skip(4.2)

        # team
        heading("YOUR TEAM   (4 / Tab = switch)")

        for c in p.team:

            mark = ">" if c is p.active_creature else " "

            text(f"{mark} {c.species}", fontweight="bold"
                 if c is p.active_creature else "normal")

            bar(30, 42, c.hp / c.max_hp,
                "#2e9e3e" if c.hp > 0 else "#888888")

            text(f"{c.hp:>3}/{c.max_hp}", x=75)

            skip(3.8)

        # battle / controls
        if p.encounter is not None:

            e = p.encounter

            heading("BATTLE!")

            text(f"Wild {e.species}", fontweight="bold", color="#b00000")

            bar(30, 42, e.hp / e.max_hp, "#d03030")

            text(f"{e.hp:>3}/{e.max_hp}", x=75)

            skip(4.5)

            text("[1] Attack  [2] Capture  [3] Run")

            skip(3.8)

            text("Capture is likelier at low HP.", size=8, color="#666666")

            skip(3.8)

        elif m.is_won():

            heading("YOU WIN!")
            text("Press R for a new game.")
            skip(3.8)

        else:

            heading("CONTROLS")

            text("Arrows / WASD  move one tile")
            skip(3.4)
            text("Click a tile    plan A* route")
            skip(3.4)
            text("Enter / click   follow the route")
            skip(3.4)
            text("Space wait   Esc cancel   R restart")
            skip(3.8)

        # AI status
        heading("WILD CREATURES (AI)")

        for c in wild:

            plan = self._plans.get(c)

            if p.encounter is c:
                state = "fighting you"
            elif plan:
                path, berry = plan
                state = (f"A* to berry {berry.pos}, "
                         f"cost {path_cost(path, m.move_cost)}")
            elif c.is_hungry:
                state = "hungry, searching"
            elif c.calm > 0:
                state = "avoiding you"
            else:
                state = "wandering"

            text(f"{c.species[:9]:<9} E{c.energy:>3}  {state}", size=8)

            skip(3.4)

        if not wild:
            text("none left", size=8)
            skip(3.4)

        # log
        heading("LOG")

        lines = []

        for entry in self.log[-8:]:
            lines.extend(textwrap.wrap(entry, 46) or [""])

        for line in lines[-8:]:

            text(line, size=8)

            skip(3.3)


# =======================================================
# START
# =======================================================

if __name__ == "__main__":

    game = Game()

    plt.show()
