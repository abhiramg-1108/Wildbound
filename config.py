# =======================================================
# WILDBOUND CONFIGURATION
# =======================================================


# -------------------------------------------------------
# WORLD (small on purpose: easy to read, easy to follow)
# -------------------------------------------------------

WIDTH = 10
HEIGHT = 10

NUM_CREATURES = 3        # wild creatures (max 4, one per species)
NUM_BERRIES = 5          # berries lying around at any time

NUM_ROCKS = 8            # impassable tiles
NUM_GRASS = 12           # tall grass tiles
GRASS_COST = 3           # normal tile = 1, tall grass = 3  (A* uses this)

BERRY_RESPAWN_EVERY = 10     # a new berry appears every N turns
MIN_START_DISTANCE = 3       # wild creatures start at least this far from you


# -------------------------------------------------------
# CREATURES
# -------------------------------------------------------

MAX_HP = 100             # your creatures
WILD_HP = 60             # wild creatures
MAX_ENERGY = 100

PLAYER_DAMAGE = (8, 16)  # damage range of your attacks
WILD_DAMAGE = (4, 10)    # damage range of wild attacks


# -------------------------------------------------------
# WILD CREATURE AI
# -------------------------------------------------------

HUNGER_PER_STEP = 1      # energy lost every turn (tall grass costs extra)
HUNGRY_BELOW = 50        # below this energy a creature looks for food
ENERGY_PER_BERRY = 40
DETECTION_RADIUS = 4     # how far a creature can "smell" berries
WANDER_CHANCE = 0.5      # a fed creature moves on half of the turns

CALM_TURNS = 5           # after you run away, the creature ignores you for a while
