from mesa import Model
from mesa.space import MultiGrid

from agents import (
    CreatureAgent,
    BerryAgent,
    PlayerAgent,
)

from config import (
    WIDTH,
    HEIGHT,
    NUM_CREATURES,
    NUM_BERRIES,
    NUM_ROCKS,
    NUM_GRASS,
    GRASS_COST,
    BERRY_RESPAWN_EVERY,
    MIN_START_DISTANCE,
)

from pathfinding import astar


# Sparkit is your starter, so wild creatures are the other four
WILD_SPECIES = ["Flameling", "Aquaff", "Leaflet", "Breezle"]


# =======================================================
# WILDBOUND MODEL
# =======================================================

class WildboundModel(Model):

    def __init__(self, seed=None):

        super().__init__(seed=seed)

        self.grid = MultiGrid(WIDTH, HEIGHT, torus=False)

        self.step_count = 0

        self.start_pos = (WIDTH // 2, HEIGHT // 2)

        # ---- terrain (re-rolled if rocks wall off the map) ----
        self.terrain = {}
        self.reachable = set()

        for _ in range(50):

            self.generate_terrain()
            self.reachable = self.compute_reachable()

            free = WIDTH * HEIGHT - NUM_ROCKS

            if len(self.reachable) >= 0.9 * free:
                break

        # ---- wild creatures (all different species, spread out) ----
        for species in self.random.sample(WILD_SPECIES, NUM_CREATURES):

            creature = CreatureAgent(
                self,
                species=species,
                energy=self.random.randint(30, 80),
            )

            self.grid.place_agent(
                creature,
                self.random_free_cell(
                    min_dist=MIN_START_DISTANCE,
                    avoid=CreatureAgent,
                ),
            )

        # ---- berries ----
        for _ in range(NUM_BERRIES):
            self.spawn_berry()

        # ---- player ----
        self.player = PlayerAgent(self)

        self.grid.place_agent(self.player, self.start_pos)

    # ===================================================
    # TERRAIN
    # ===================================================

    def generate_terrain(self):

        cells = [
            (x, y)
            for x in range(WIDTH)
            for y in range(HEIGHT)
            if (x, y) != self.start_pos
        ]

        self.random.shuffle(cells)

        self.terrain = {}

        for pos in cells[:NUM_ROCKS]:
            self.terrain[pos] = "rock"

        for pos in cells[NUM_ROCKS:NUM_ROCKS + NUM_GRASS]:
            self.terrain[pos] = "grass"

    def compute_reachable(self):
        """Tiles the player can walk to from the start (flood fill)."""

        seen = {self.start_pos}
        todo = [self.start_pos]

        while todo:

            x, y = todo.pop()

            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):

                n = (x + dx, y + dy)

                if (
                    n not in seen
                    and 0 <= n[0] < WIDTH
                    and 0 <= n[1] < HEIGHT
                    and self.move_cost(n) is not None
                ):
                    seen.add(n)
                    todo.append(n)

        return seen

    def move_cost(self, pos):
        """Cost of entering a tile. None = blocked."""

        kind = self.terrain.get(pos)

        if kind == "rock":
            return None

        if kind == "grass":
            return GRASS_COST

        return 1

    def find_path(self, start, goal, moore=False):
        """A* route over this world's terrain."""

        return astar(
            start, goal, WIDTH, HEIGHT, self.move_cost, moore=moore
        )

    # ===================================================
    # PLACING THINGS
    # ===================================================

    def cell_has(self, pos, agent_type):

        return any(
            isinstance(a, agent_type)
            for a in self.grid.get_cell_list_contents([pos])
        )

    def random_free_cell(self, min_dist=0, avoid=None):
        """A reachable tile (optionally far from the start, and
        without an agent of type `avoid`)."""

        sx, sy = self.start_pos

        cells = [
            pos for pos in self.reachable
            if max(abs(pos[0] - sx), abs(pos[1] - sy)) >= min_dist
            and (avoid is None or not self.cell_has(pos, avoid))
        ]

        return self.random.choice(sorted(cells))

    def spawn_berry(self):

        berry = BerryAgent(self)

        self.grid.place_agent(
            berry,
            self.random_free_cell(avoid=BerryAgent),
        )

    # ===================================================
    # QUERIES
    # ===================================================

    def wild_creatures(self):

        return [
            a for a in self.agents
            if isinstance(a, CreatureAgent)
            and not a.player_owned
            and a.hp > 0
            and a.pos is not None
        ]

    def berries(self):

        return [
            a for a in self.agents
            if isinstance(a, BerryAgent) and a.pos is not None
        ]

    def is_won(self):
        """The game is won when no wild creature is left."""

        return len(self.wild_creatures()) == 0

    # ===================================================
    # ASCII MAP (terminal version)
    # ===================================================

    def print_map(self, path=None):

        path_tiles = set(path) if path else set()

        print()

        wild = {c.pos for c in self.wild_creatures()}
        berries = {b.pos for b in self.berries()}

        for y in range(HEIGHT - 1, -1, -1):

            row = f"{y:2} "

            for x in range(WIDTH):

                pos = (x, y)

                if pos == self.player.pos:
                    symbol = "@"
                elif pos in wild:
                    symbol = "C"
                elif pos in path_tiles:
                    symbol = "*"
                elif pos in berries:
                    symbol = "b"
                elif self.terrain.get(pos) == "rock":
                    symbol = "#"
                elif self.terrain.get(pos) == "grass":
                    symbol = '"'
                else:
                    symbol = "."

                row += symbol + " "

            print(row)

        print("   " + " ".join(str(x % 10) for x in range(WIDTH)))

        print(
            "\n@ you  C wild  b berry  # rock  "
            "\" tall grass  * route"
        )

    # ===================================================
    # ONE TURN OF THE WORLD
    # ===================================================

    def step(self):

        print(f"\n========== TURN {self.step_count + 1} ==========")

        # wild creatures and berries act in random order ...
        self.agents.select(lambda a: a is not self.player).shuffle_do("step")

        # ... then the player checks who ended up next to them
        self.player.step()

        self.step_count += 1

        if (
            self.step_count % BERRY_RESPAWN_EVERY == 0
            and len(self.berries()) < NUM_BERRIES
        ):
            self.spawn_berry()


# =======================================================
# QUICK CHECK:  python model.py
# =======================================================

if __name__ == "__main__":

    model = WildboundModel()

    for _ in range(30):
        model.step()

    print(f"\nWild left: {len(model.wild_creatures())}, "
          f"berries: {len(model.berries())}")
