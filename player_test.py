from model import WildboundModel
from pathfinding import path_cost


# =======================================================
# CREATE GAME
# =======================================================

model = WildboundModel()

player = model.player


print("\n======================")
print("      WILDBOUND")
print("======================")


print(
    f"Player starting position: "
    f"{player.pos}"
)


print(
    f"Your starter is "
    f"{player.starter.species}!"
)


print(
    f"HP: "
    f"{player.starter.hp}/"
    f"{player.starter.max_hp}"
)


model.print_map()


# =======================================================
# MAIN GAME LOOP
# =======================================================

for step in range(50):

    print(
        "\n----------------------"
    )


    print(
        f"Player Position: "
        f"{player.pos}"
    )


    print(
        f"Active Creature: "
        f"{player.active_creature.species}"
    )


    print(
        f"HP: "
        f"{player.active_creature.hp}/"
        f"{player.active_creature.max_hp}"
    )


    print(
        f"Team: "
        f"{player.team_names()}"
    )


    # ===================================================
    # BATTLE MODE
    # ===================================================

    if player.encounter:

        wild = player.encounter


        print(
            f"\n⚡ WILD "
            f"{wild.species}!"
        )


        print(
            f"Wild HP: "
            f"{wild.hp}/"
            f"{wild.max_hp}"
        )


        print(
            "\nWhat do you want to do?"
        )


        print(
            "1. ⚔️ Attack"
        )

        print(
            "2. 🎯 Capture"
        )

        print(
            "3. 🏃 Run"
        )


        choice = input(
            "\nYour choice: "
        )


        # -----------------------------------------------
        # ATTACK
        # -----------------------------------------------

        if choice == "1":

            player.attack()


        # -----------------------------------------------
        # CAPTURE
        # -----------------------------------------------

        elif choice == "2":

            player.attempt_capture()


        # -----------------------------------------------
        # RUN
        # -----------------------------------------------

        elif choice == "3":

            player.run_away()


        else:

            print(
                "❌ Invalid choice."
            )


        # -----------------------------------------------
        # CHECK IF ACTIVE CREATURE FAINTED
        # -----------------------------------------------

        if (
            player.encounter
            and
            player.active_creature.hp <= 0
        ):

            print(
                "\nYour active creature "
                "has fainted."
            )


            available = []


            for creature in player.team:

                if creature.hp > 0:

                    available.append(
                        creature
                    )


            # -------------------------------------------
            # ANOTHER CREATURE AVAILABLE
            # -------------------------------------------

            if available:

                print(
                    "\nChoose another "
                    "creature:"
                )


                for i, creature in enumerate(
                    player.team
                ):

                    if creature.hp > 0:

                        print(
                            f"{i}. "
                            f"{creature.species} "
                            f"HP="
                            f"{creature.hp}/"
                            f"{creature.max_hp}"
                        )


                try:

                    index = int(
                        input(
                            "Enter team number: "
                        )
                    )


                    player.choose_active_creature(
                        index
                    )


                except ValueError:

                    print(
                        "❌ Please enter "
                        "a number."
                    )


            # -------------------------------------------
            # EVERY CREATURE FAINTED
            # -------------------------------------------

            else:

                player.handle_faint()


        continue


    # ===================================================
    # EXPLORATION MODE
    # ===================================================

    print(
        "\nMove:"
    )


    print(
        "W = Up"
    )

    print(
        "S = Down"
    )

    print(
        "A = Left"
    )

    print(
        "D = Right"
    )

    print(
        "M = Show map"
    )

    print(
        "T = Travel to a tile (A* plans the route)"
    )

    print(
        "Q = Quit"
    )


    move = input(
        "Your move: "
    ).lower()


    if move == "q":

        print(
            "\n🏁 Game ended."
        )

        break


    # ---------------------------------------------------
    # SHOW MAP
    # ---------------------------------------------------

    if move == "m":

        model.print_map()

        continue


    # ---------------------------------------------------
    # TRAVEL: A* suggests, the player decides
    # ---------------------------------------------------

    if move == "t":

        try:

            goal = (
                int(input("Target x: ")),
                int(input("Target y: "))
            )

        except ValueError:

            print(
                "❌ Please enter numbers."
            )

            continue


        path = player.plan_path(
            goal
        )


        if path is None:

            print(
                "❌ No route to that tile "
                "(rock, off the map, or walled in)."
            )

            continue


        cost = path_cost(
            path,
            model.move_cost
        )


        model.print_map(path)


        print(
            f"\nRoute: {len(path) - 1} steps, "
            f"cost {cost}"
        )


        answer = input(
            "Follow this route? (y/n): "
        ).lower()


        if answer == "y":

            # follow_path already lets the world
            # act after every tile
            player.follow_path(
                path
            )


        continue


    if move == "w":

        player.move(
            "up"
        )


    elif move == "s":

        player.move(
            "down"
        )


    elif move == "a":

        player.move(
            "left"
        )


    elif move == "d":

        player.move(
            "right"
        )


    else:

        print(
            "❌ Invalid movement."
        )

        continue


    # -----------------------------------------------
    # LET WILD WORLD ACT
    # -----------------------------------------------

    model.step()


# =======================================================
# GAME END
# =======================================================

print(
    "\n======================"
)

print(
    "      GAME END"
)

print(
    "======================"
)


print(
    f"Final position: "
    f"{player.pos}"
)


print(
    f"Final team: "
    f"{player.team_names()}"
)
