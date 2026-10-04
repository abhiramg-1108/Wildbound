from model import WildboundModel
from agents import CreatureAgent


# =======================================================
# CREATE MODEL
# =======================================================

model = WildboundModel()


print(
    "WILDBOUND SIMULATION"
)

print(
    "---------------------"
)


# =======================================================
# RUN SIMULATION
# =======================================================

for step in range(20):

    model.step()


    print(
        f"\nStep {step + 1}"
    )


    # -----------------------------------------------
    # DISPLAY WILD CREATURES
    # -----------------------------------------------

    for agent in model.agents:

        if (
            isinstance(
                agent,
                CreatureAgent
            )
            and
            not agent.player_owned
        ):

            print(
                f"{agent.species:10} "
                f"Position={agent.pos} "
                f"HP={agent.hp} "
                f"Energy={agent.energy} "
                f"Personality={agent.personality}"
            )


    # -----------------------------------------------
    # DISPLAY PLAYER
    # -----------------------------------------------

    player = model.player


    print(
        f"Player Position="
        f"{player.pos}"
    )


    print(
        f"Active Creature="
        f"{player.active_creature.species} "
        f"HP="
        f"{player.active_creature.hp}/"
        f"{player.active_creature.max_hp}"
    )


    print(
        f"Team="
        f"{player.team_names()}"
    )