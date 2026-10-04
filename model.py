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
    NUM_BERRIES
)


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


            x = self.random.randrange(WIDTH)
            y = self.random.randrange(HEIGHT)


            self.grid.place_agent(
                creature,
                (x, y)
            )


        # -----------------------------------------------
        # CREATE BERRIES
        # -----------------------------------------------

        for i in range(NUM_BERRIES):

            berry = BerryAgent(self)


            x = self.random.randrange(WIDTH)
            y = self.random.randrange(HEIGHT)


            self.grid.place_agent(
                berry,
                (x, y)
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