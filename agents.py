from mesa import Agent

from config import (
    MAX_HP,
    WILD_HP,
    MAX_ENERGY,
    PLAYER_DAMAGE,
    WILD_DAMAGE,
    HUNGER_PER_STEP,
    HUNGRY_BELOW,
    ENERGY_PER_BERRY,
    DETECTION_RADIUS,
    WANDER_CHANCE,
    CALM_TURNS,
)

from pathfinding import path_cost


# =======================================================
# BERRY
# =======================================================

class BerryAgent(Agent):

    def __init__(self, model):
        super().__init__(model)

    def step(self):
        pass

    def remove(self):

        if self.pos is not None:
            self.model.grid.remove_agent(self)

        super().remove()


# =======================================================
# CREATURE (wild or owned by the player)
# =======================================================

class CreatureAgent(Agent):

    def __init__(
        self,
        model,
        species,
        max_hp=WILD_HP,
        energy=MAX_ENERGY,
        player_owned=False,
    ):

        super().__init__(model)

        self.species = species
        self.max_hp = max_hp
        self.hp = max_hp
        self.energy = energy
        self.player_owned = player_owned

        # After the player runs away, the creature ignores
        # the player for this many turns (so "Run" really works)
        self.calm = 0

    # ---------------------------------------------------
    # state
    # ---------------------------------------------------

    @property
    def is_hungry(self):
        return self.energy < HUNGRY_BELOW

    # ===================================================
    # WILD CREATURE AI  (one decision per turn)
    #
    #   1. lose a little energy
    #   2. standing on a berry and hungry enough -> eat it
    #   3. hungry -> A* to the cheapest reachable berry
    #   4. otherwise wander (only half of the turns)
    # ===================================================

    def step(self):

        if self.player_owned or self.hp <= 0:
            return

        player = getattr(self.model, "player", None)

        # The world holds its breath during a fight
        if player is not None and player.encounter is self:
            return

        if self.calm > 0:
            self.calm -= 1

        self.energy = max(0, self.energy - HUNGER_PER_STEP)

        if self.try_eat():
            return

        if self.is_hungry:

            plan = self.plan_food_route()

            if plan is not None:

                path, _berry = plan
                next_pos = path[1]

                # never walk onto the player's tile; wait instead
                if player is None or next_pos != player.pos:
                    self.move_to(next_pos)
                    self.try_eat()

                return

            # hungry but nothing reachable nearby: keep searching
            self.wander()
            self.try_eat()
            return

        if self.model.random.random() < WANDER_CHANCE:
            self.wander()
            self.try_eat()

    # ---------------------------------------------------
    # food
    # ---------------------------------------------------

    def find_nearby_berries(self):

        cells = self.model.grid.get_neighborhood(
            self.pos,
            moore=True,
            include_center=True,
            radius=DETECTION_RADIUS,
        )

        return [
            obj
            for cell in cells
            for obj in self.model.grid.get_cell_list_contents([cell])
            if isinstance(obj, BerryAgent)
        ]

    def plan_food_route(self):
        """
        A* to every berry in range; pick the CHEAPEST route
        (tall grass counts), not just the closest berry.
        Returns (path, berry) or None.

        The visualisation calls this too, so what you see
        is exactly what the creature will do.
        """

        best = None

        for berry in self.find_nearby_berries():

            if berry.pos == self.pos:
                continue

            path = self.model.find_path(self.pos, berry.pos, moore=True)

            if path is None or len(path) < 2:
                continue

            cost = path_cost(path, self.model.move_cost)

            if best is None or cost < best[0]:
                best = (cost, path, berry)

        if best is None:
            return None

        return best[1], best[2]

    def try_eat(self):
        """Eat a berry on this tile, unless it would be wasted."""

        if self.energy > MAX_ENERGY - ENERGY_PER_BERRY:
            return False

        for obj in self.model.grid.get_cell_list_contents([self.pos]):

            if isinstance(obj, BerryAgent):

                self.energy = min(MAX_ENERGY, self.energy + ENERGY_PER_BERRY)

                obj.remove()

                print(f"{self.species} ate a berry.")

                return True

        return False

    # ---------------------------------------------------
    # movement
    # ---------------------------------------------------

    def move_to(self, pos):

        cost = self.model.move_cost(pos)

        self.model.grid.move_agent(self, pos)

        # tall grass is tiring: pay the extra cost in energy
        self.energy = max(0, self.energy - (cost - 1))

    def wander(self):

        player = getattr(self.model, "player", None)

        steps = [
            pos
            for pos in self.model.grid.get_neighborhood(
                self.pos, moore=True, include_center=False
            )
            if self.model.move_cost(pos) is not None
            and (player is None or pos != player.pos)
        ]

        if steps:
            self.move_to(self.model.random.choice(steps))

    # ---------------------------------------------------
    # health
    # ---------------------------------------------------

    def take_damage(self, damage):
        self.hp = max(0, self.hp - damage)

    def heal(self):
        self.hp = self.max_hp
        self.energy = MAX_ENERGY

    def remove(self):

        if self.pos is not None:
            self.model.grid.remove_agent(self)

        super().remove()


# =======================================================
# PLAYER
# =======================================================

DIRECTIONS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


class PlayerAgent(Agent):

    def __init__(self, model):

        super().__init__(model)

        self.encounter = None            # wild creature we are fighting
        self.captured_creatures = []     # species names caught so far
        self.defeated = 0                # wild creatures knocked out

        self.starter = CreatureAgent(
            model,
            species="Sparkit",
            max_hp=MAX_HP,
            player_owned=True,
        )

        self.team = [self.starter]
        self.active_creature = self.starter

    # ---------------------------------------------------
    # turn
    # ---------------------------------------------------

    def step(self):

        # The player is controlled from outside; each turn we
        # only check whether a wild creature came close.
        if self.encounter is None:

            creature = self.check_for_encounter()

            if creature:
                self.start_encounter(creature)

    # ===================================================
    # MOVEMENT
    # ===================================================

    def move(self, direction):
        """Move one tile. Returns True if the player moved."""

        if self.encounter is not None:
            print("Finish the battle first!")
            return False

        if direction not in DIRECTIONS:
            print("Invalid direction!")
            return False

        dx, dy = DIRECTIONS[direction]
        new_pos = (self.pos[0] + dx, self.pos[1] + dy)

        inside = (
            0 <= new_pos[0] < self.model.grid.width
            and 0 <= new_pos[1] < self.model.grid.height
        )

        if not inside:
            print("You cannot leave the map.")
            return False

        if self.model.move_cost(new_pos) is None:
            print("A rock blocks the way.")
            return False

        self.model.grid.move_agent(self, new_pos)

        creature = self.check_for_encounter()

        if creature:
            self.start_encounter(creature)

        return True

    def step_to(self, pos):
        """Move onto a neighbouring tile (used when following a route)."""

        delta = (pos[0] - self.pos[0], pos[1] - self.pos[1])

        for name, d in DIRECTIONS.items():
            if d == delta:
                return self.move(name)

        return False

    # ---------------------------------------------------
    # A* travel (optional - the player stays in control)
    # ---------------------------------------------------

    def plan_path(self, goal):
        """Ask A* for a route. Does NOT move the player."""

        return self.model.find_path(self.pos, goal, moore=False)

    def follow_path(self, path):
        """
        Walk a route one tile at a time (terminal version).
        The world acts after every tile; walking stops as
        soon as an encounter starts.
        """

        for next_pos in path[1:]:

            if not self.step_to(next_pos):
                print("Route blocked, stopping.")
                return

            self.model.step()

            if self.encounter:
                print("Travel interrupted!")
                return

        print(f"Arrived at {self.pos}.")

    # ===================================================
    # ENCOUNTERS
    # ===================================================

    def check_for_encounter(self):

        cells = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=True, radius=1
        )

        for cell in cells:

            for obj in self.model.grid.get_cell_list_contents([cell]):

                if (
                    isinstance(obj, CreatureAgent)
                    and not obj.player_owned
                    and obj.hp > 0
                    and obj.calm == 0
                ):
                    return obj

        return None

    def start_encounter(self, creature):

        if self.encounter is not None:
            return

        self.encounter = creature

        print(f"A wild {creature.species} appeared!")

    # ===================================================
    # BATTLE
    # ===================================================

    def attack(self):

        if self.encounter is None:
            return False

        wild = self.encounter
        attacker = self.active_creature

        damage = self.model.random.randint(*PLAYER_DAMAGE)

        wild.take_damage(damage)

        print(
            f"{attacker.species} hit {wild.species} for {damage}. "
            f"({wild.hp}/{wild.max_hp} HP left)"
        )

        if wild.hp <= 0:

            print(f"Wild {wild.species} fainted!")

            wild.remove()

            self.defeated += 1
            self.encounter = None

            return True

        self.wild_attack()

        return True

    def wild_attack(self):

        if self.encounter is None:
            return

        wild = self.encounter
        defender = self.active_creature

        damage = self.model.random.randint(*WILD_DAMAGE)

        defender.take_damage(damage)

        print(
            f"Wild {wild.species} hit {defender.species} for {damage}. "
            f"({defender.hp}/{defender.max_hp} HP left)"
        )

        if defender.hp <= 0:
            self.handle_faint()

    def attempt_capture(self):

        if self.encounter is None:
            return False

        creature = self.encounter

        # full HP -> 25%,  almost 0 HP -> 90%
        ratio = creature.hp / creature.max_hp
        chance = 0.25 + 0.65 * (1 - ratio)

        print(f"Capture chance: {chance * 100:.0f}%")

        if self.model.random.random() < chance:

            print(f"{creature.species} was captured!")

            creature.player_owned = True
            creature.heal()
            creature.remove()          # leaves the map, joins the team

            self.team.append(creature)
            self.captured_creatures.append(creature.species)

            self.encounter = None

            return True

        print(f"{creature.species} broke free!")

        self.wild_attack()

        return False

    def run_away(self):

        if self.encounter is None:
            return False

        print(f"You escaped from {self.encounter.species}.")

        # it loses interest for a few turns, otherwise the
        # next move would start the same fight again
        self.encounter.calm = CALM_TURNS
        self.encounter = None

        return True

    # ===================================================
    # TEAM
    # ===================================================

    def alive_team(self):
        return [c for c in self.team if c.hp > 0]

    def choose_active_creature(self, index):

        if not 0 <= index < len(self.team):
            print("Invalid team choice!")
            return False

        creature = self.team[index]

        if creature.hp <= 0:
            print(f"{creature.species} has fainted!")
            return False

        self.active_creature = creature

        print(f"Go, {creature.species}!")

        return True

    def next_creature(self):
        """Switch to the next healthy team member."""

        n = len(self.team)
        start = self.team.index(self.active_creature)

        for i in range(1, n):

            candidate = self.team[(start + i) % n]

            if candidate.hp > 0:
                self.active_creature = candidate
                print(f"Go, {candidate.species}!")
                return True

        print("No other healthy creature.")
        return False

    def handle_faint(self):
        """
        The active creature fainted.
        - another one is healthy -> it is sent out automatically
        - nobody is left        -> back to camp, team healed
        """

        fainted = self.active_creature

        print(f"{fainted.species} fainted!")

        alive = self.alive_team()

        if alive:

            self.active_creature = alive[0]

            print(f"Go, {self.active_creature.species}!")

            return True

        print("All your creatures fainted! Back to camp.")

        if self.encounter is not None:
            self.encounter.calm = CALM_TURNS

        self.encounter = None

        self.model.grid.move_agent(self, self.model.start_pos)

        self.heal_team()

        return False

    def heal_team(self):

        for creature in self.team:
            creature.heal()

        self.active_creature = self.starter

        print("Your team was healed.")

    # ---------------------------------------------------

    def team_names(self):

        return [
            f"{c.species} ({c.hp}/{c.max_hp} HP)"
            for c in self.team
        ]
