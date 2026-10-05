# =======================================================
# A* PATHFINDING
# =======================================================
#
# A* explores tiles in order of   f(n) = g(n) + h(n)
#
#   g(n) = real cost paid to reach tile n from the start
#   h(n) = heuristic: optimistic guess of the cost left
#          from n to the goal
#
# If h never overestimates the real remaining cost, A*
# is guaranteed to return the cheapest path.
#
# Every tile costs at least 1 to enter, so:
#   - 4-direction movement -> Manhattan distance works
#   - 8-direction movement -> Chebyshev distance works
# =======================================================

import heapq


def astar(start, goal, width, height, cost_fn, moore=False):
    """
    Find the cheapest path from start to goal.

    start, goal : (x, y) tuples
    width,height: size of the grid
    cost_fn(pos): cost of ENTERING pos, or None if blocked
    moore       : True  -> 8 directions (diagonals allowed)
                  False -> 4 directions

    Returns a list of positions [start, ..., goal],
    or None if the goal cannot be reached.
    """

    if start == goal:
        return [start]

    # Goal inside a rock (or off the map) -> impossible
    if cost_fn(goal) is None:
        return None

    if moore:
        directions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
    else:
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]


    def heuristic(pos):

        dx = abs(pos[0] - goal[0])
        dy = abs(pos[1] - goal[1])

        if moore:
            return max(dx, dy)

        return dx + dy


    # Priority queue of (f, g, position)
    open_list = [(heuristic(start), 0, start)]

    came_from = {start: None}     # for rebuilding the path
    best_g = {start: 0}           # cheapest known cost to each tile

    while open_list:

        f, g, current = heapq.heappop(open_list)

        # Goal reached -> walk backwards to build the path
        if current == goal:

            path = []

            while current is not None:
                path.append(current)
                current = came_from[current]

            path.reverse()

            return path

        # Outdated queue entry (a cheaper route was found later)
        if g > best_g[current]:
            continue

        for dx, dy in directions:

            neighbour = (current[0] + dx, current[1] + dy)

            # Stay inside the map
            if not (0 <= neighbour[0] < width
                    and 0 <= neighbour[1] < height):
                continue

            step_cost = cost_fn(neighbour)

            # Blocked tile
            if step_cost is None:
                continue

            new_g = g + step_cost

            if neighbour not in best_g or new_g < best_g[neighbour]:

                best_g[neighbour] = new_g
                came_from[neighbour] = current

                heapq.heappush(
                    open_list,
                    (new_g + heuristic(neighbour), new_g, neighbour)
                )

    # Open list ran out: no route exists
    return None


def path_cost(path, cost_fn):
    """Total cost of walking a path (the start tile is free)."""

    return sum(cost_fn(pos) for pos in path[1:])
