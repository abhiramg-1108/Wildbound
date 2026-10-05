import random

from mesa import Model
from mesa.space import MultiGrid

from agents import (
    CreatureAgent,
    BerryAgent,
    PlayerAgent
)

from config import (
    WIDTH,
    HEIGHT,
    NUM_CREATURES,
    NUM_BERRIES,
    NUM_ROCKS,
    NUM_GRASS,
    GRASS_COST
)

from pathfinding import astar


# =======================================================
# WILDBOUND MODEL
# =======================================================

class WildboundModel(Model):

    def __init__(self):

        super().__init__()


        # -----------------------------------------------
        # CREATE GAME WORLD
        # -----------------------------------------------

        self.grid = MultiGrid(
            WIDTH,
            HEIGHT,
            torus=False
        )


        self.step_count = 0


        # -----------------------------------------------
        # CREATE TERRAIN (rocks and tall grass)
        # -----------------------------------------------

        self.terrain = {}

        self.generate_terrain()


        # -----------------------------------------------
        # CREATE WILD CREATURES
        # -----------------------------------------------

        species = [
            "Sparkit",
            "Flameling",
            "Aquaff",
            "Leaflet",
            "Breezle"
        ]


        for i in range(NUM_CREATURES):

            creature = CreatureAgent(
                self,
                species=random.choice(species)
            )


            self.grid.place_agent(
                creature,
                self.random_free_cell()
            )


        # -----------------------------------------------
        # CREATE BERRIES
        # -----------------------------------------------

        for i in range(NUM_BERRIES):

            berry = BerryAgent(self)


            self.grid.place_agent(
                berry,
                self.random_free_cell()
            )


        # -----------------------------------------------
        # CREATE PLAYER
        # -----------------------------------------------

        self.player = PlayerAgent(
            self
        )


        self.grid.place_agent(
            self.player,
            (
                WIDTH // 2,
                HEIGHT // 2
            )
        )


        # -----------------------------------------------
        # STARTER MESSAGE
        # -----------------------------------------------

        print(
            "\n⚡ Your starter Pokémon is "
            f"{self.player.starter.species}!"
        )


        print(
            f"❤️ HP: "
            f"{self.player.starter.hp}/"
            f"{self.player.starter.max_hp}"
        )


    # ===================================================
    # TERRAIN
    # ===================================================

    def generate_terrain(self):

        start = (WIDTH // 2, HEIGHT // 2)

        for terrain, amount in (
            ("rock", NUM_ROCKS),
            ("grass", NUM_GRASS)
        ):

            placed = 0

            while placed < amount:

                pos = (
                    self.random.randrange(WIDTH),
                    self.random.randrange(HEIGHT)
                )

                # Keep the player's start tile clear
                if pos == start or pos in self.terrain:
                    continue

                self.terrain[pos] = terrain

                placed += 1


    def move_cost(self, pos):
        """Cost of entering a tile. None = blocked."""

        kind = self.terrain.get(pos)

        if kind == "rock":
            return None

        if kind == "grass":
            return GRASS_COST

        return 1


    def random_free_cell(self):

        while True:

            pos = (
                self.random.randrange(WIDTH),
                self.random.randrange(HEIGHT)
            )

            if self.move_cost(pos) is not None:
                return pos


    def find_path(self, start, goal, moore=False):
        """A* route over this world's terrain."""

        return astar(
            start,
            goal,
            WIDTH,
            HEIGHT,
            self.move_cost,
            moore=moore
        )


    # ===================================================
    # ASCII MAP (for the terminal version)
    # ===================================================

    def print_map(self, path=None):

        path_tiles = set(path) if path else set()

        print()

        for y in range(HEIGHT - 1, -1, -1):

            row = f"{y:2} "

            for x in range(WIDTH):

                pos = (x, y)

                contents = self.grid.get_cell_list_contents([pos])

                if self.player in contents:
                    symbol = "@"

                elif any(
                    type(a).__name__ == "CreatureAgent"
                    and not a.player_owned
                    and a.hp > 0
                    for a in contents
                ):
                    symbol = "C"

                elif pos in path_tiles:
                    symbol = "*"

                elif any(
                    type(a).__name__ == "BerryAgent"
                    for a in contents
                ):
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
    # SIMULATION STEP
    # ===================================================

    def step(self):

        print(
            f"\n========== STEP "
            f"{self.step_count + 1} =========="
        )


        self.agents.shuffle_do(
            "step"
        )


        self.step_count += 1


# =======================================================
# TEST MODEL DIRECTLY
# =======================================================

if __name__ == "__main__":

    model = WildboundModel()


    for i in range(30):

        model.step()


        print(
            f"Active agents: "
            f"{len(model.agents)}"
        )
