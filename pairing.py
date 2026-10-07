import random


def make_pairs(items):
    """Shuffle a list of people into teams of two.

    If the number of people is odd, the last team gets three people
    (instead of leaving someone out). With fewer than 2 people there is
    nobody to pair, so we return an empty list.

    Example: 5 people -> [[a, b], [c, d, e]]
    """
    # Copy the list so we don't shuffle the caller's original list
    people = list(items)
    random.shuffle(people)

    if len(people) < 2:
        return []

    # Slice the shuffled list into pairs: [0:2], [2:4], [4:6], ...
    # The range stops at len - 1 so an odd leftover person isn't a team of one
    teams = [people[i:i + 2] for i in range(0, len(people) - 1, 2)]

    # If someone is left over (odd number of people), add them to the last team
    if len(people) % 2 == 1:
        teams[-1].append(people[-1])

    return teams
