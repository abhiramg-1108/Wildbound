import random

from mesa import Agent

from config import (
    MAX_HP,
    MAX_ENERGY,
    DETECTION_RADIUS
)


# =======================================================
# BERRY AGENT
# =======================================================

class BerryAgent(Agent):

    def __init__(self, model):
        super().__init__(model)


    def step(self):

        pass


    def remove(self):

        if self.pos is not None:

            self.model.grid.remove_agent(
                self
            )

        super().remove()


# =======================================================
# CREATURE AGENT
# =======================================================

class CreatureAgent(Agent):

    def __init__(
        self,
        model,
        species,
        hp=MAX_HP,
        energy=MAX_ENERGY,
        player_owned=False
    ):

        super().__init__(model)

        self.species = species
        self.hp = hp
        self.energy = energy

        # Maximum HP
        self.max_hp = MAX_HP

        # Creature stats
        self.attack = random.randint(
            10,
            20
        )

        self.speed = random.randint(
            1,
            2
        )

        # Personality still exists as an
        # AI characteristic
        self.personality = random.choice([
            "aggressive",
            "timid",
            "neutral"
        ])

        # Battle cooldown
        self.cooldown = 0

        # Is this creature part of
        # the player's team?
        self.player_owned = player_owned

        # Experience
        self.xp = 0


    # ===================================================
    # WILD CREATURE AI
    # ===================================================

    def step(self):

        # Player-owned creatures do not
        # wander independently.
        if self.player_owned:

            return


        # Defeated wild creatures do nothing
        if self.hp <= 0:

            return


        # -----------------------------------------------
        # FIND FOOD WHEN HUNGRY
        # -----------------------------------------------

        if self.energy < 50:

            berries = self.find_nearby_berries()


            if berries:

                nearest_berry = self.find_nearest(
                    berries
                )


                if nearest_berry.pos == self.pos:

                    self.eat(
                        nearest_berry
                    )

                else:

                    self.move_towards(
                        nearest_berry.pos
                    )

                return


        # -----------------------------------------------
        # CHECK FOR BERRY ON CURRENT CELL
        # -----------------------------------------------

        contents = self.model.grid.get_cell_list_contents(
            [self.pos]
        )


        for obj in contents:

            if isinstance(
                obj,
                BerryAgent
            ):

                self.eat(obj)

                return


        # -----------------------------------------------
        # OTHERWISE WANDER
        # -----------------------------------------------

        self.wander()


    # ===================================================
    # FIND NEARBY BERRIES
    # ===================================================

    def find_nearby_berries(self):

        nearby_cells = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=False,
            radius=DETECTION_RADIUS
        )


        berries = []


        for cell in nearby_cells:

            contents = self.model.grid.get_cell_list_contents(
                [cell]
            )


            for obj in contents:

                if isinstance(
                    obj,
                    BerryAgent
                ):

                    berries.append(obj)


        return berries


    # ===================================================
    # FIND NEAREST OBJECT
    # ===================================================

    def find_nearest(self, objects):

        if not objects:

            return None


        return min(
            objects,
            key=lambda obj:
            abs(
                obj.pos[0]
                -
                self.pos[0]
            )
            +
            abs(
                obj.pos[1]
                -
                self.pos[1]
            )
        )


    # ===================================================
    # MOVE TOWARDS TARGET
    # ===================================================

    def move_towards(self, target):

        possible_steps = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=False
        )


        if not possible_steps:

            return


        best_step = min(
            possible_steps,
            key=lambda pos:
            abs(
                pos[0]
                -
                target[0]
            )
            +
            abs(
                pos[1]
                -
                target[1]
            )
        )


        self.model.grid.move_agent(
            self,
            best_step
        )


        self.energy -= 2


        if self.energy < 0:

            self.energy = 0


    # ===================================================
    # WANDER
    # ===================================================

    def wander(self):

        possible_steps = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=False
        )


        if possible_steps:

            new_position = random.choice(
                possible_steps
            )


            self.model.grid.move_agent(
                self,
                new_position
            )


            self.energy -= 1


            if self.energy < 0:

                self.energy = 0


    # ===================================================
    # EAT BERRY
    # ===================================================

    def eat(self, berry):

        self.energy += 30


        if self.energy > MAX_ENERGY:

            self.energy = MAX_ENERGY


        berry.remove()


        print(
            f"🍓 {self.species} ate a berry"
        )


    # ===================================================
    # TAKE DAMAGE
    # ===================================================

    def take_damage(self, damage):

        self.hp -= damage


        if self.hp < 0:

            self.hp = 0


    # ===================================================
    # GAIN XP
    # ===================================================

    def gain_xp(self, amount):

        self.xp += amount


        print(
            f"⭐ {self.species} gained "
            f"{amount} XP!"
        )


    # ===================================================
    # HEAL
    # ===================================================

    def heal(self):

        self.hp = self.max_hp

        self.energy = MAX_ENERGY


        print(
            f"💚 {self.species} was healed!"
        )


    # ===================================================
    # REMOVE CREATURE
    # ===================================================

    def remove(self):

        if self.pos is not None:

            self.model.grid.remove_agent(
                self
            )


        super().remove()


# =======================================================
# PLAYER AGENT
# =======================================================

class PlayerAgent(Agent):

    def __init__(self, model):

        super().__init__(model)


        # Current encounter
        self.encounter = None


        # Captured creature names
        self.captured_creatures = []


        # -----------------------------------------------
        # STARTER CREATURE
        # -----------------------------------------------

        self.starter = CreatureAgent(
            model,
            species="Sparkit",
            player_owned=True
        )


        # -----------------------------------------------
        # PLAYER TEAM
        # -----------------------------------------------

        self.team = [
            self.starter
        ]


        # -----------------------------------------------
        # ACTIVE CREATURE
        # -----------------------------------------------

        self.active_creature = self.starter


    # ===================================================
    # PLAYER STEP
    # ===================================================

    def step(self):

        # Player is controlled externally.
        # We only check for nearby encounters.

        if self.encounter is None:

            creature = self.check_for_encounter()


            if creature:

                self.start_encounter(
                    creature
                )


    # ===================================================
    # PLAYER MOVEMENT
    # ===================================================

    def move(self, direction):

        x, y = self.pos


        if direction == "up":

            new_position = (
                x,
                y + 1
            )


        elif direction == "down":

            new_position = (
                x,
                y - 1
            )


        elif direction == "left":

            new_position = (
                x - 1,
                y
            )


        elif direction == "right":

            new_position = (
                x + 1,
                y
            )


        else:

            print(
                "Invalid direction!"
            )

            return


        # -----------------------------------------------
        # MAP BOUNDARY CHECK
        # -----------------------------------------------

        if (
            0 <= new_position[0]
            <
            self.model.grid.width

            and

            0 <= new_position[1]
            <
            self.model.grid.height
        ):

            self.model.grid.move_agent(
                self,
                new_position
            )


            print(
                f"👤 Player moved to "
                f"{self.pos}"
            )


        else:

            print(
                "🚧 Player cannot move "
                "outside the map!"
            )


        # -----------------------------------------------
        # CHECK ENCOUNTER
        # -----------------------------------------------

        if self.encounter is None:

            creature = self.check_for_encounter()


            if creature:

                self.start_encounter(
                    creature
                )


    # ===================================================
    # CHECK FOR ENCOUNTER
    # ===================================================

    def check_for_encounter(self):

        nearby_cells = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=False,
            radius=1
        )


        for cell in nearby_cells:

            contents = self.model.grid.get_cell_list_contents(
                [cell]
            )


            for obj in contents:

                if isinstance(
                    obj,
                    CreatureAgent
                ):

                    if (
                        not obj.player_owned
                        and
                        obj.hp > 0
                    ):

                        return obj


        return None


    # ===================================================
    # START ENCOUNTER
    # ===================================================

    def start_encounter(self, creature):

        if self.encounter is not None:

            return


        self.encounter = creature


        print(
            "\n⚡ WILD ENCOUNTER!"
        )


        print(
            f"A wild {creature.species} "
            f"appeared!"
        )


        print(
            f"❤️ Wild {creature.species}: "
            f"{creature.hp}/"
            f"{creature.max_hp} HP"
        )


        print(
            f"⚡ Your "
            f"{self.active_creature.species}: "
            f"{self.active_creature.hp}/"
            f"{self.active_creature.max_hp} HP"
        )


    # ===================================================
    # PLAYER'S CREATURE ATTACKS
    # ===================================================

    def attack(self):

        if self.encounter is None:

            return False


        if self.active_creature.hp <= 0:

            print(
                f"❌ {self.active_creature.species} "
                f"is fainted!"
            )

            return False


        wild = self.encounter

        attacker = self.active_creature


        damage = random.randint(
            attacker.attack // 2,
            attacker.attack
        )


        wild.take_damage(
            damage
        )


        attacker.gain_xp(10)


        print(
            f"⚔️ {attacker.species} attacked "
            f"{wild.species} "
            f"for {damage} damage!"
        )


        print(
            f"❤️ Wild {wild.species}: "
            f"{wild.hp}/"
            f"{wild.max_hp} HP"
        )


        # -----------------------------------------------
        # WILD CREATURE DEFEATED
        # -----------------------------------------------

        if wild.hp <= 0:

            print(
                f"💀 Wild {wild.species} "
                f"fainted!"
            )


            attacker.gain_xp(20)


            wild.remove()


            self.encounter = None


            return True


        # -----------------------------------------------
        # WILD CREATURE RETALIATES
        # -----------------------------------------------

        self.wild_attack()


        return True


    # ===================================================
    # WILD CREATURE ATTACK
    # ===================================================

    def wild_attack(self):

        if self.encounter is None:

            return


        wild = self.encounter

        defender = self.active_creature


        damage = random.randint(
            5,
            15
        )


        defender.take_damage(
            damage
        )


        print(
            f"🐾 Wild {wild.species} attacked "
            f"{defender.species} "
            f"for {damage} damage!"
        )


        print(
            f"❤️ {defender.species}: "
            f"{defender.hp}/"
            f"{defender.max_hp} HP"
        )


        # -----------------------------------------------
        # PLAYER CREATURE FAINTS
        # -----------------------------------------------

        if defender.hp <= 0:

            print(
                f"💫 {defender.species} "
                f"fainted!"
            )


            self.handle_faint()


    # ===================================================
    # CAPTURE
    # ===================================================

    def attempt_capture(self):

        if self.encounter is None:

            return False


        creature = self.encounter


        # -----------------------------------------------
        # CAPTURE CHANCE
        # -----------------------------------------------

        hp_ratio = (
            creature.hp
            /
            creature.max_hp
        )


        # Full HP  -> 20%
        # 75 HP    -> 37.5%
        # 50 HP    -> 55%
        # 25 HP    -> 72.5%
        # 0 HP     -> 90%

        capture_chance = (
            0.20
            +
            (1 - hp_ratio)
            * 0.70
        )


        print(
            f"🎯 Capture chance: "
            f"{capture_chance * 100:.1f}%"
        )


        roll = random.random()


        # -----------------------------------------------
        # CAPTURE SUCCESS
        # -----------------------------------------------

        if roll < capture_chance:

            print(
                f"🎉 {creature.species} "
                f"was captured!"
            )


            # Mark as player-owned
            creature.player_owned = True


            # Add to team
            self.team.append(
                creature
            )


            self.captured_creatures.append(
                creature.species
            )


            # Restore energy
            creature.energy = MAX_ENERGY


            # Remove from wild world
            creature.remove()


            self.encounter = None


            print(
                f"📦 Team: "
                f"{self.team_names()}"
            )


            return True


        # -----------------------------------------------
        # CAPTURE FAILURE
        # -----------------------------------------------

        else:

            print(
                f"❌ {creature.species} "
                f"escaped the capture!"
            )


            # Failed capture uses the player's turn
            self.wild_attack()


            return False


    # ===================================================
    # SWITCH ACTIVE CREATURE
    # ===================================================

    def choose_active_creature(self, index):

        if (
            index < 0
            or
            index >= len(self.team)
        ):

            print(
                "❌ Invalid team choice!"
            )

            return False


        creature = self.team[index]


        if creature.hp <= 0:

            print(
                f"❌ {creature.species} "
                f"is fainted!"
            )

            return False


        self.active_creature = creature


        print(
            f"🔄 Go, "
            f"{creature.species}!"
        )


        return True


    # ===================================================
    # HANDLE FAINT
    # ===================================================

    def handle_faint(self):

        available = []


        for creature in self.team:

            if creature.hp > 0:

                available.append(
                    creature
                )


        # -----------------------------------------------
        # ANOTHER CREATURE AVAILABLE
        # -----------------------------------------------

        if available:

            print(
                "\n⚠️ Your active creature "
                "has fainted."
            )


            print(
                "Choose another creature "
                "from your team."
            )


            return True


        # -----------------------------------------------
        # EVERY CREATURE FAINTED
        # -----------------------------------------------

        print(
            "\n💔 All your creatures "
            "have fainted!"
        )


        print(
            "🏕️ You retreat to "
            "the healing point."
        )


        self.encounter = None


        # For the prototype, automatically
        # heal the team so the player does
        # not get permanently stuck.
        self.heal_team()


        return False


    # ===================================================
    # HEAL TEAM
    # ===================================================

    def heal_team(self):

        print(
            "\n🏥 Your team is being healed..."
        )


        for creature in self.team:

            creature.heal()


        # Starter becomes active again
        self.active_creature = self.starter


        print(
            f"⚡ "
            f"{self.active_creature.species} "
            f"is ready to battle again!"
        )


    # ===================================================
    # RUN AWAY
    # ===================================================

    def run_away(self):

        if self.encounter:

            print(
                f"🏃 Escaped from "
                f"{self.encounter.species}!"
            )


        self.encounter = None


    # ===================================================
    # TEAM DISPLAY
    # ===================================================

    def team_names(self):

        names = []


        for creature in self.team:

            names.append(
                f"{creature.species} "
                f"({creature.hp}/"
                f"{creature.max_hp} HP)"
            )


        return names