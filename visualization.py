# =======================================================
# WILDBOUND VISUALIZATION  (Mesa 3.x + Solara + Matplotlib)
#
# Run with:   solara run visualization.py
#
# The map is drawn by our own Matplotlib code (draw_world)
# and shown through solara.FigureMatplotlib.  This avoids
# the SpaceRenderer / post_process machinery entirely, so
# there is nothing version-specific that can leave the page
# blank.  Mesa's SolaraViz still provides Step / Play /
# Reset and drives model.step().
# =======================================================

import contextlib
import io
import sys

# Windows consoles often use cp1252 and crash on emoji
# prints (the model / agents print a lot of them).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import solara
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from mesa.visualization import SolaraViz
from mesa.visualization.utils import force_update, update_counter

from agents import BerryAgent, CreatureAgent
from config import MAX_ENERGY
from model import WildboundModel
from pathfinding import path_cost


HUNGRY_BELOW = 50          # same threshold as CreatureAgent.step

SPECIES_COLORS = {
    "Sparkit": "gold",
    "Flameling": "orangered",
    "Aquaff": "deepskyblue",
    "Leaflet": "forestgreen",
    "Breezle": "mediumpurple",
}


# =======================================================
# HELPERS
# =======================================================

def wild_creatures(model):
    return [
        a for a in model.agents
        if isinstance(a, CreatureAgent)
        and not a.player_owned
        and a.hp > 0
        and a.pos is not None
    ]


def berries(model):
    return [
        a for a in model.agents
        if isinstance(a, BerryAgent) and a.pos is not None
    ]


def hungry_route(model, creature):
    """
    The route a hungry creature would take, using the same
    rules as CreatureAgent.step (berries within detection
    radius, closest first, first one A* can reach).
    Returns (path, berry_position) or (None, None).
    """

    if creature.energy >= HUNGRY_BELOW:
        return None, None

    near = creature.find_nearby_berries()

    near.sort(
        key=lambda b: abs(b.pos[0] - creature.pos[0])
        + abs(b.pos[1] - creature.pos[1])
    )

    for berry in near:

        if berry.pos == creature.pos:
            return None, None          # it will just eat

        path = model.find_path(creature.pos, berry.pos, moore=True)

        if path is not None and len(path) >= 2:
            return path, berry.pos

    return None, None


# =======================================================
# MAP DRAWING
# =======================================================

def draw_world(model, plan=None):

    W = model.grid.width
    H = model.grid.height
    player = model.player

    fig = Figure(figsize=(7.4, 7.8))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.13)

    ax.set_facecolor("#f3ecd8")
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal", adjustable="box")

    # ---- terrain ------------------------------------------
    for (x, y), kind in model.terrain.items():

        if kind == "rock":

            ax.add_patch(Rectangle(
                (x, y), 1, 1,
                facecolor="#6b6b6b", edgecolor="#222222",
                linewidth=0.8, zorder=1))

            ax.add_patch(Rectangle(
                (x + 0.22, y + 0.22), 0.56, 0.56,
                facecolor="#8f8f8f", edgecolor="none", zorder=1.1))

        elif kind == "grass":

            ax.add_patch(Rectangle(
                (x, y), 1, 1,
                facecolor="#a8dd9a", edgecolor="#7fbf72",
                linewidth=0.5, zorder=0.8))

    # ---- player's planned route ---------------------------
    if plan and len(plan) >= 2:

        ax.plot(
            [p[0] + 0.5 for p in plan],
            [p[1] + 0.5 for p in plan],
            linestyle="-", linewidth=3, marker="o", markersize=4,
            color="royalblue", alpha=0.85, zorder=5)

        ax.scatter(
            plan[-1][0] + 0.5, plan[-1][1] + 0.5,
            s=260, marker="X", color="royalblue", zorder=5.5)

    # ---- A* routes of hungry wild creatures ---------------
    wild = wild_creatures(model)

    for c in wild:

        path, target = hungry_route(model, c)

        if path is None:
            continue

        ax.plot(
            [p[0] + 0.5 for p in path],
            [p[1] + 0.5 for p in path],
            linestyle="--", linewidth=2.2, marker="o", markersize=3,
            color="darkorange", alpha=0.95, zorder=6)

        ax.scatter(
            target[0] + 0.5, target[1] + 0.5,
            s=330, marker="*", facecolors="none",
            edgecolors="darkorange", linewidths=2, zorder=7)

    # ---- berries ------------------------------------------
    for b in berries(model):

        ax.add_patch(Circle(
            (b.pos[0] + 0.5, b.pos[1] + 0.5), 0.22,
            facecolor="crimson", edgecolor="#7a0019",
            linewidth=1, zorder=8))

    # ---- wild creatures -----------------------------------
    for c in wild:

        hungry = c.energy < HUNGRY_BELOW
        in_battle = player.encounter is c

        ax.add_patch(Circle(
            (c.pos[0] + 0.5, c.pos[1] + 0.5), 0.36,
            facecolor=SPECIES_COLORS.get(c.species, "royalblue"),
            edgecolor="red" if in_battle
            else ("darkorange" if hungry else "black"),
            linewidth=3 if (hungry or in_battle) else 1,
            zorder=9))

        ax.text(
            c.pos[0] + 0.5, c.pos[1] + 0.5, c.species[0],
            ha="center", va="center", fontsize=8,
            fontweight="bold", color="black", zorder=9.5)

    # ---- player -------------------------------------------
    if player.pos is not None:

        px, py = player.pos

        ax.add_patch(Circle(
            (px + 0.5, py + 0.5), 0.42,
            facecolor="black",
            edgecolor="red" if player.encounter else "white",
            linewidth=3, zorder=12))

        ax.text(
            px + 0.5, py + 0.5, "P",
            ha="center", va="center", fontsize=9,
            fontweight="bold", color="white", zorder=13)

    # ---- axes, grid, title --------------------------------
    ax.set_xticks([i + 0.5 for i in range(W)])
    ax.set_xticklabels([str(i) for i in range(W)], fontsize=7)
    ax.set_yticks([i + 0.5 for i in range(H)])
    ax.set_yticklabels([str(i) for i in range(H)], fontsize=7)
    ax.tick_params(length=0)

    ax.set_xticks(range(W + 1), minor=True)
    ax.set_yticks(range(H + 1), minor=True)
    ax.grid(which="minor", color="black", alpha=0.12, linewidth=0.6)
    ax.tick_params(which="minor", length=0)

    ax.set_title(
        f"WILDBOUND  -  step {model.step_count}",
        fontsize=14, fontweight="bold")

    # ---- legend -------------------------------------------
    def dot(color, label, marker="o", edge="black"):
        return Line2D([0], [0], marker=marker, linestyle="None",
                      markerfacecolor=color, markeredgecolor=edge,
                      markersize=9, label=label)

    handles = [
        dot("black", "Player"),
        dot("gold", "Wild creature (letter = species)"),
        dot("gold", "Hungry", edge="darkorange"),
        dot("crimson", "Berry"),
        dot("#6b6b6b", "Rock", marker="s"),
        dot("#a8dd9a", "Tall grass", marker="s", edge="#7fbf72"),
        Line2D([0], [0], color="darkorange", linestyle="--",
               label="A* route to food"),
        Line2D([0], [0], color="royalblue", label="Your planned route"),
    ]

    ax.legend(
        handles=handles, loc="upper center",
        bbox_to_anchor=(0.5, -0.05), ncol=3,
        fontsize=8, frameon=False)

    return fig


# =======================================================
# UI HELPERS
# =======================================================

def act(model, fn):
    """
    Run a game action, capture what the game print()s and
    keep it in a small on-screen log, then refresh the UI.
    """

    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        fn()

    log = getattr(model, "ui_log", None)

    if log is None:
        log = []
        model.ui_log = log

    for line in buffer.getvalue().splitlines():

        line = line.strip()

        if line and not line.startswith("="):
            log.append(line)

    del log[:-12]

    force_update()


# =======================================================
# RIGHT-HAND CONTROL PANEL
# =======================================================

@solara.component
def ControlPanel(model, plan, set_plan):

    update_counter.get()

    tx, set_tx = solara.use_state(0)
    ty, set_ty = solara.use_state(0)

    player = model.player
    active = player.active_creature
    in_battle = player.encounter is not None

    wild = wild_creatures(model)
    hungry = [c for c in wild if c.energy < HUNGRY_BELOW]

    # ---- actions ------------------------------------------
    def move(direction):

        def do():
            if player.move(direction):
                model.step()

        set_plan(None)
        act(model, do)

    def plan_route():

        path = player.plan_path((tx, ty))

        def do():
            if path is None:
                print("No route to that tile (rock, off-map, walled in).")
            else:
                print(f"Route planned: {len(path) - 1} steps, "
                      f"cost {path_cost(path, model.move_cost)}")

        set_plan(path)
        act(model, do)

    def follow_route():

        route = plan
        set_plan(None)
        act(model, lambda: player.follow_path(route))

    # ---- layout -------------------------------------------
    with solara.Column(style={"min-width": "310px", "max-width": "360px"}):

        solara.Markdown("## 👤 Player")

        solara.Markdown(
            f"**Position:** `{player.pos}`  \n"
            f"**Active:** {active.species}  \n"
            f"**HP:** {active.hp}/{active.max_hp}  \n"
            f"**Energy:** {active.energy}/{MAX_ENERGY}"
        )

        # movement
        solara.Markdown("### Movement")

        with solara.Row(justify="center"):
            solara.Button("↑", on_click=lambda: move("up"),
                          disabled=in_battle)

        with solara.Row(justify="center"):
            solara.Button("←", on_click=lambda: move("left"),
                          disabled=in_battle)
            solara.Button("↓", on_click=lambda: move("down"),
                          disabled=in_battle)
            solara.Button("→", on_click=lambda: move("right"),
                          disabled=in_battle)

        # A* travel
        solara.Markdown("### Travel (A*)")

        with solara.Row():
            solara.InputInt("x", value=tx, on_value=set_tx)
            solara.InputInt("y", value=ty, on_value=set_ty)

        with solara.Row():
            solara.Button("Plan route", on_click=plan_route,
                          disabled=in_battle)
            solara.Button("Follow route", on_click=follow_route,
                          color="primary",
                          disabled=in_battle or not plan)

        # encounter
        solara.Markdown("### ⚔️ Encounter")

        if in_battle:

            enemy = player.encounter

            solara.Markdown(
                f"**Wild {enemy.species}**  \n"
                f"HP: {enemy.hp}/{enemy.max_hp}"
            )

            with solara.Row():
                solara.Button("Attack", color="primary",
                              on_click=lambda: act(model, player.attack))
                solara.Button("Capture",
                              on_click=lambda: act(model, player.attempt_capture))
                solara.Button("Run",
                              on_click=lambda: act(model, player.run_away))

        else:
            solara.Markdown("No encounter. Walk next to a wild creature.")

        # team
        solara.Markdown("### 👥 Team")

        for i, c in enumerate(player.team):

            mark = "💚" if c.hp > 0 else "💀"
            tag = "  **(active)**" if c is active else ""

            solara.Markdown(
                f"{mark} {i}. {c.species} - "
                f"HP {c.hp}/{c.max_hp}{tag}")

            if c.hp > 0 and c is not active:
                solara.Button(
                    f"Switch to {c.species}",
                    on_click=lambda i=i: act(
                        model, lambda: player.choose_active_creature(i)))

        # world + AI
        solara.Markdown("### 🌍 World")

        solara.Markdown(
            f"**Wild creatures:** {len(wild)}  \n"
            f"**Hungry:** {len(hungry)}  \n"
            f"**Berries:** {len(berries(model))}"
        )

        solara.Markdown("### 🧠 AI status")

        shown = False

        for c in hungry:

            path, target = hungry_route(model, c)

            if path:

                solara.Markdown(
                    f"**{c.species}** is seeking food  \n"
                    f"Energy: {c.energy}/{MAX_ENERGY}  \n"
                    f"Target berry: `{target}`  \n"
                    f"A* steps: {len(path) - 1}, "
                    f"cost: {path_cost(path, model.move_cost)}"
                )

                shown = True
                break

        if not shown:
            solara.Markdown(
                "No hungry creature has a reachable berry nearby - "
                "they wander until one comes within range.")

        # log
        solara.Markdown("### 📜 Log")

        for line in reversed(getattr(model, "ui_log", [])[-8:]):
            solara.Text(line, style={"font-size": "12px"})


# =======================================================
# WILDBOUND GAME PAGE
# =======================================================

# IMPORTANT:
# We intentionally do NOT use Mesa's SolaraViz / SpaceRenderer here.
# The game is rendered directly with Solara + Matplotlib.
# Mesa still runs the actual model, agents, AI, A* and battles.

GAME_MODEL = solara.reactive(WildboundModel())


@solara.component
def GamePage():

    update_counter.get()

    model = GAME_MODEL.value

    plan, set_plan = solara.use_state(None)
    playing, set_playing = solara.use_state(False)

    # ---------------------------------------------------
    # AUTOPLAY
    # ---------------------------------------------------

    async def autoplay():
        import asyncio

        while playing:
            await asyncio.sleep(0.7)

            if not playing:
                break

            model.step()
            force_update()

    solara.lab.use_task(
        autoplay,
        dependencies=[playing],
        prefer_threaded=False,
        raise_error=False,
    )

    # ---------------------------------------------------
    # GLOBAL ACTIONS
    # ---------------------------------------------------

    def step_model():
        model.step()
        force_update()

    def toggle_play():
        set_playing(not playing)

    def reset_model():
        set_playing(False)
        GAME_MODEL.value = WildboundModel()
        set_plan(None)
        force_update()

    # ---------------------------------------------------
    # HEADER
    # ---------------------------------------------------

    solara.Title("Wildbound - Agent-Based Creature Adventure")

    with solara.Column(
        style={
            "padding": "18px",
            "width": "100%",
            "box-sizing": "border-box",
        }
    ):

        solara.Markdown(
            "# ⚡ WILDBOUND\n"
            "### Agent-Based Creature Adventure"
        )

        solara.Markdown(
            "Mesa-powered autonomous creatures • A* pathfinding • "
            "manual player control • encounters & capture"
        )

        with solara.Row(
            style={
                "align-items": "flex-start",
                "gap": "24px",
                "width": "100%",
                "flex-wrap": "wrap",
            }
        ):

            # =================================================
            # MAP
            # =================================================

            with solara.Column(
                style={
                    "flex": "1 1 700px",
                    "min-width": "620px",
                }
            ):

                with solara.Card():
                    solara.FigureMatplotlib(
                        draw_world(model, plan),
                        format="png",
                        dependencies=[update_counter.value],
                    )

            # =================================================
            # CONTROLS
            # =================================================

            with solara.Column(
                style={
                    "flex": "0 1 360px",
                    "min-width": "320px",
                    "max-width": "380px",
                }
            ):

                # Simulation controls
                with solara.Card("Simulation"):

                    with solara.Row():
                        solara.Button(
                            "RESET",
                            color="primary",
                            on_click=reset_model,
                        )

                        solara.Button(
                            "⏸ PAUSE" if playing else "▶ PLAY",
                            color="primary",
                            on_click=toggle_play,
                        )

                        solara.Button(
                            "STEP",
                            color="primary",
                            on_click=step_model,
                            disabled=playing,
                        )

                    solara.Markdown(
                        f"**Simulation step:** {model.step_count}  "
                        f"\n**Status:** {'▶ Running' if playing else '⏸ Paused'}"
                    )

                # Existing game controls
                ControlPanel(model, plan, set_plan)


# Solara uses the variable named `page` as the application entry point.
page = GamePage

page
