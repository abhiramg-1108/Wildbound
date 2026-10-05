import heapq
import random

from pathfinding import astar, path_cost


# =======================================================
# HELPERS
# =======================================================

def make_cost_fn(rocks=(), grass=(), grass_cost=3):

    rocks = set(rocks)
    grass = set(grass)

    def cost_fn(pos):

        if pos in rocks:
            return None

        if pos in grass:
            return grass_cost

        return 1

    return cost_fn


def dijkstra_cost(start, goal, w, h, cost_fn, moore):
    """Reference answer: A* without a heuristic."""

    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    if moore:
        dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    best = {start: 0}
    queue = [(0, start)]

    while queue:

        g, cur = heapq.heappop(queue)

        if cur == goal:
            return g

        if g > best[cur]:
            continue

        for dx, dy in dirs:

            n = (cur[0] + dx, cur[1] + dy)

            if not (0 <= n[0] < w and 0 <= n[1] < h):
                continue

            c = cost_fn(n)

            if c is None:
                continue

            if n not in best or g + c < best[n]:
                best[n] = g + c
                heapq.heappush(queue, (g + c, n))

    return None


def greedy_walk(start, goal, w, h, cost_fn, max_steps=100):
    """
    The ORIGINAL move_towards idea: always step to the
    neighbour closest (Manhattan) to the target.
    (Rocks are skipped so it can't walk through them.)
    """

    pos = start

    for _ in range(max_steps):

        if pos == goal:
            return pos, True

        options = [
            (pos[0] + dx, pos[1] + dy)
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)
        ]

        options = [
            o for o in options
            if 0 <= o[0] < w and 0 <= o[1] < h
            and cost_fn(o) is not None
        ]

        pos = min(
            options,
            key=lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1])
        )

    return pos, False


# =======================================================
# TESTS
# =======================================================

def test_empty_grid():

    cost = make_cost_fn()

    path = astar((0, 0), (5, 3), 10, 10, cost)

    assert path[0] == (0, 0) and path[-1] == (5, 3)
    assert len(path) - 1 == 8          # Manhattan distance
    print("✓ empty grid: shortest path found")


def test_wall_detour():

    wall = [(5, y) for y in range(0, 9)]      # gap at y = 9
    cost = make_cost_fn(rocks=wall)

    path = astar((2, 2), (8, 2), 10, 10, cost)

    assert path is not None
    assert not any(p in wall for p in path)
    assert (5, 9) in path                      # goes through the gap
    print("✓ wall: path detours through the gap")


def test_unreachable():

    box = [(4, 3), (4, 4), (4, 5), (5, 3), (5, 5), (6, 3), (6, 4), (6, 5)]
    cost = make_cost_fn(rocks=box)

    assert astar((0, 0), (5, 4), 10, 10, cost) is None     # walled in
    assert astar((0, 0), (4, 4), 10, 10, cost) is None     # goal is a rock
    print("✓ unreachable goals return None")


def test_grass_is_avoided():

    # Direct row is tall grass (cost 3 each), a one-tile detour is cheaper
    grass = [(x, 2) for x in range(1, 8)]
    cost = make_cost_fn(grass=grass)

    path = astar((0, 2), (8, 2), 10, 10, cost)

    assert path_cost(path, cost) < 3 * 7       # beats walking through grass
    print(f"✓ weighted terrain: cost {path_cost(path, cost)} "
          f"instead of {3 * 7 + 1} through the grass")


def test_matches_dijkstra():

    rng = random.Random(1)

    for moore in (False, True):

        for _ in range(200):

            w = h = 12

            rocks = {(rng.randrange(w), rng.randrange(h)) for _ in range(30)}
            grass = {(rng.randrange(w), rng.randrange(h)) for _ in range(30)}
            cost = make_cost_fn(rocks, grass - rocks)

            start = (rng.randrange(w), rng.randrange(h))
            goal = (rng.randrange(w), rng.randrange(h))

            if start in rocks or goal in rocks:
                continue

            expected = dijkstra_cost(start, goal, w, h, cost, moore)
            path = astar(start, goal, w, h, cost, moore=moore)

            if expected is None:
                assert path is None
            else:
                assert path_cost(path, cost) == expected

    print("✓ 400 random maps: A* cost == Dijkstra cost (optimal)")


def test_greedy_vs_astar():

    # U-shaped trap: the berry is behind the bottom of a U
    rocks = (
        [(x, 6) for x in range(3, 8)]
        + [(3, y) for y in range(3, 7)]
        + [(7, y) for y in range(3, 7)]
    )
    cost = make_cost_fn(rocks=rocks)

    start, berry = (5, 4), (5, 8)           # inside the U, berry above it

    end, reached = greedy_walk(start, berry, 12, 12, cost)
    path = astar(start, berry, 12, 12, cost, moore=True)

    print(f"  greedy : stuck at {end} after 100 steps, reached={reached}")
    print(f"  A*     : reached in {len(path) - 1} steps")

    assert not reached
    assert path is not None
    print("✓ greedy gets trapped, A* finds the way out")


if __name__ == "__main__":

    test_empty_grid()
    test_wall_detour()
    test_unreachable()
    test_grass_is_avoided()
    test_matches_dijkstra()
    test_greedy_vs_astar()

    print("\nAll pathfinding tests passed.")
