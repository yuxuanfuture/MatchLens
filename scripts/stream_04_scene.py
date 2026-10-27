"""Authored actions and positional anchors for the fourth synthetic stream."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NUMBERS = (1, 2, 4, 5, 3, 6, 8, 10, 7, 9, 11)


@dataclass(frozen=True)
class Action:
    kind: str
    start: int
    end: int
    actor: str | None
    origin: tuple[float, float]
    target: tuple[float, float]
    receiver: str | None = None
    number: int | None = None
    outcome: str = "complete"
    extra: dict[str, Any] = field(default_factory=dict)


def action(kind, start, end, actor, origin, target, **kwargs):
    return Action(kind, round(start * 1000), round(end * 1000), actor,
                  origin, target, **kwargs)


def actions():
    passes = [
        (1, 1, 3, "A4", (33, 25), (38, 43), "A5"),
        (2, 4, 6, "A5", (40, 44), (45, 55), "A3"),
        (3, 7, 9, "A3", (48, 54), (52, 36), "A6"),
        (4, 10, 12, "A6", (55, 34), (60, 13), "A2"),
        (5, 13, 15, "A2", (62, 15), (67, 28), "A8"),
        (6, 16.5, 18, "A8", (69, 27), (73, 22.5), "A7"),
        (7, 19.5, 21, "U7", (71, 24), (61, 30), "U9"),
        (8, 21.5, 24, "U9", (60, 31), (57, 44), "U8"),
        (9, 25, 27, "U8", (58, 46), (69, 55), "U3"),
        (10, 28, 30, "U3", (71, 54), (78, 44), "U5"),
        (11, 31, 33, "U5", (79, 42), (80, 27), "U4"),
        (12, 34, 36, "U4", (78, 28), (68, 33), "U6"),
        (13, 37, 39, "U6", (66, 32), (61, 23), "U10"),
        (14, 40, 42, "U10", (62, 21), (72, 12), "U2"),
        (15, 42.5, 44.5, "U2", (72, 14), (68, 31), "U6"),
        (16, 46.5, 48, "A6", (74, 32), (80, 28), "A10"),
        (17, 49, 51, "A10", (82, 28), (85, 32), "A9"),
        (18, 52, 54, "A9", (85, 32), (83, 43), "A8"),
        (19, 56, 57, "A8", (87, 44), (90, 46), "A7"),
        (20, 60, 62, "A7", (92, 44), (90, 34), "A10"),
        (21, 64, 66, "A10", (92, 32), (94, 42), "A7"),
        (22, 66, 68, "A7", (94, 42), (93, 31), "A9"),
        (23, 74, 75.5, "U4", (90, 32), (72, 38), "U6"),
        (24, 78, 80, "U6", (63, 36), (48, 29), "U10"),
        (25, 83, 85.5, "U10", (40, 31), (25, 34), "U9"),
    ]
    result = []
    for number, start, end, actor, origin, target, receiver in passes:
        extra = {"intended_end_position": {"x": 77, "y": 18},
                 "intercepted_by_id": "U7"} if number == 6 else {}
        result.append(action("pass", start, end, actor, origin, target,
                             receiver=receiver, number=number,
                             outcome="incomplete" if number == 6 else "complete",
                             extra=extra))
    carries = [
        (0, 1, "A4", (30, 24), (33, 25)),
        (3, 4, "A5", (38, 43), (40, 44)),
        (6, 7, "A3", (45, 55), (48, 54)),
        (9, 10, "A6", (52, 36), (55, 34)),
        (12, 13, "A2", (60, 13), (62, 15)),
        (15, 16.5, "A8", (67, 28), (69, 27)),
        (18.5, 19.5, "U7", (73, 22.5), (71, 24)),
        (21, 21.5, "U9", (61, 30), (60, 31)),
        (24, 25, "U8", (57, 44), (58, 46)),
        (27, 28, "U3", (69, 55), (71, 54)),
        (30, 31, "U5", (78, 44), (79, 42)),
        (33, 34, "U4", (80, 27), (78, 28)),
        (36, 37, "U6", (68, 33), (66, 32)),
        (39, 40, "U10", (61, 23), (62, 21)),
        (42, 42.5, "U2", (72, 12), (72, 14)),
        (45.5, 46.5, "A6", (70, 32), (74, 32)),
        (48, 49, "A10", (80, 28), (82, 28)),
        (54, 56, "A8", (83, 43), (87, 44)),
        (57, 60, "A7", (90, 46), (92, 44)),
        (62, 64, "A10", (90, 34), (92, 32)),
        (68, 71, "A9", (93, 31), (94, 31)),
        (72.5, 74, "U4", (93, 32), (90, 32)),
        (75.5, 78, "U6", (72, 38), (63, 36)),
        (80, 83, "U10", (48, 29), (40, 31)),
        (85.5, 87.5, "U9", (25, 34), (13, 34)),
        (88.5, 89.5, "U9", (9.5, 39), (7, 38)),
    ]
    result.extend(action("carry", *entry) for entry in carries)
    result.extend([
        action("hold", 51, 52, "A9", (85, 32), (85, 32)),
        action("hold", 71, 72, "A9", (94, 31), (94, 31)),
        action("carry", 44.5, 45, "U6", (68, 31), (70, 32),
               outcome="lost_control", extra={"actor_end_position": (69, 31)}),
        action("carry", 87.5, 88.5, "U9", (13, 34), (9.5, 39),
               extra={"action": "take_on", "opponent_id": "A1",
                      "outcome": "complete"}),
        action("loose", 18, 18.5, None, (73, 22.5), (73, 22.5)),
        action("loose", 45, 45.5, None, (70, 32), (70, 32)),
        action("loose", 72, 72.5, None, (94, 31), (93, 32)),
        action("shot", 89.5, 90, "U9", (7, 38), (0, 34)),
    ])
    return sorted(result, key=lambda item: (item.start, item.end))


# Each row follows NUMBERS exactly. Action constraints replace off-ball anchors.
PHASE_POSITIONS = {
    0: {
        "A": [(6,34),(52,13),(30,24),(36,43),(38,55),(45,36),(61,28),(66,34),(72,18),(75,34),(68,57)],
        "U": [(99,34),(84,12),(86,27),(86,44),(78,55),(70,34),(61,45),(66,20),(76,25),(62,30),(60,8)],
    },
    18500: {
        "A": [(6,34),(62,15),(38,24),(42,43),(48,54),(55,34),(69,27),(70,36),(77,18),(78,34),(72,57)],
        "U": [(99,34),(82,12),(84,28),(83,43),(76,54),(65,34),(59,44),(64,20),(73,22.5),(61,30),(60,8)],
    },
    45500: {
        "A": [(6,34),(58,12),(47,25),(49,43),(58,55),(70,32),(78,43),(78,28),(85,46),(82,32),(75,58)],
        "U": [(99,34),(79,15),(87,30),(87,39),(85,50),(69,31),(76,44),(72,24),(78,20),(60,30),(66,8)],
    },
    57000: {
        "A": [(6,34),(66,13),(54,25),(55,43),(66,55),(77,34),(87,44),(88,30),(90,46),(90,31),(84,57)],
        "U": [(99,34),(94,14),(95,29),(94,34),(88,48),(82,36),(84,44),(77,24),(85,20),(62,31),(67,8)],
    },
    72000: {
        "A": [(6,34),(70,12),(53,44),(56,24),(71,55),(78,34),(88,44),(92,32),(94,42),(94,31),(90,57)],
        "U": [(99,34),(94,13),(94,31),(95,35),(94,46),(78,37),(84,44),(65,26),(88,20),(57,33),(62,8)],
    },
    83000: {
        "A": [(6.4,34),(47,14),(33.4,44),(36.4,24),(48,54),(50,35),(72,44),(76,32),(78,42),(80,31),(78,56)],
        "U": [(99,34),(88,13),(71,33),(86,35),(88,49),(49,38),(75,44),(40,31),(80,20),(34,34),(44,8)],
    },
    90000: {
        "A": [(9.5,33),(36,15),(9,35),(11,29),(36,53),(39,34),(58,44),(62,32),(65,42),(69,31),(66,56)],
        "U": [(99,34),(84,13),(58,34),(80,35),(84,49),(30,37),(70,44),(34,32),(73,20),(4.5,39),(37,9)],
    },
    99000: {
        "A": [(3,34),(36,16),(18,36),(20,29),(37,52),(43,35),(54,44),(57,32),(60,42),(61,31),(59,55)],
        "U": [(99,34),(82,14),(56,34),(77,35),(82,49),(36,38),(68,44),(24,40),(70,20),(17,40),(42,10)],
    },
    115000: {
        "A": [(2,34),(42,13),(33,25),(34,43),(42,55),(47,34),(48,44),(49,30),(50,22),(52.5,34),(49,57)],
        "U": [(99,34),(78,14),(57,34),(76,43),(78,53),(63,34),(65,45),(58,39),(58,20),(53.5,38),(56,10)],
    },
    120000: {
        "A": [(5,34),(43,14),(36,25),(37,43),(43,54),(48,34),(49,44),(50,30),(50.5,23),(52.5,34),(50,56)],
        "U": [(98,34),(79,14),(58,34),(77,43),(79,53),(64,34),(66,44),(57,38),(59,20),(55,36),(57,11)],
    },
}

PRESSURES = ((25000, "A8", "U8"), (44500, "A6", "U6"),
             (59000, "U3", "A7"), (63000, "U5", "A10"))


def build_paths(sequence):
    paths = {f"{team}{number}": {} for team in ("A", "U") for number in NUMBERS}
    for time, teams in PHASE_POSITIONS.items():
        for team, positions in teams.items():
            for number, position in zip(NUMBERS, positions):
                paths[f"{team}{number}"][time] = position
    for item in sequence:
        if item.actor:
            paths[item.actor][item.start] = item.origin
            if item.kind in {"carry", "hold"}:
                paths[item.actor][item.end] = item.extra.get("actor_end_position", item.target)
        if item.kind == "pass":
            target = (77, 18) if item.outcome == "incomplete" else item.target
            paths[item.receiver][item.end] = target
    specific = {
        "A8": {25000: (60,45)},
        "A6": {44500: (66.3,31.5),45500: (70,32)},
        "U7": {18000: (73,22.5),18500: (73,22.5)},
        "U3": {59000: (93,45.5)},
        "U5": {63000: (93,33.4)},
        "U4": {71000: (96,33),72000: (94,31),72500: (93,32)},
        "A4": {84000: (36,39),85500: (32,35),87500: (21,35),89500: (11,35)},
        "A5": {85500: (31,28),87500: (22,28),89500: (13,29)},
        "A1": {85500: (10,34),87500: (11,34),88000: (12,32),
               88500: (12,31.5),89500: (10.5,32),116000: (0,34)},
    }
    for player, anchors in specific.items():
        paths[player].update(anchors)
    return paths


def interpolate(anchors, time):
    ordered = sorted(anchors.items())
    if time <= ordered[0][0]:
        return ordered[0][1]
    for (start, origin), (end, target) in zip(ordered, ordered[1:]):
        if time <= end:
            ratio = (time - start) / (end - start)
            return tuple(a + (b - a) * ratio for a, b in zip(origin, target))
    return ordered[-1][1]


def ball_at(sequence, paths, time):
    if time >= 90000:
        owner = "A1" if time >= 116000 else None
        position = interpolate(paths[owner], time) if owner else (0,34)
        return position, owner, None, "dead", False
    item = next(item for item in sequence if item.start <= time < item.end)
    ratio = (time - item.start) / (item.end - item.start)
    position = tuple(a + (b - a) * ratio for a, b in zip(item.origin, item.target))
    if item.kind == "loose":
        return position, None, None, "loose", True
    if item.kind == "shot":
        return position, None, None, "shot_flight", True
    if item.kind == "pass":
        return position, None, item.actor[0], "pass_flight", True
    if item.outcome == "lost_control":
        owner = item.actor if time == item.start else None
        return position, owner, item.actor[0], "in_play", True
    return interpolate(paths[item.actor], time), item.actor, item.actor[0], "in_play", True
