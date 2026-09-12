"""Buildings and floors, derived from the room name.

The routine carries no floor field -- the room name is the only thing that
encodes location, and it does so reliably:

    KT-318(A)  ->  building KT,   floor 3
    ANX1-101   ->  building ANX1, floor 1
    G1-001     ->  building G1,   ground floor
    EMBED      ->  no zone (a named lab, not a numbered room)

So zones are computed from the room string rather than stored. That keeps them
correct when a routine is revised, and means changing the rule here fixes every
screen at once instead of needing 30,000 rows re-stamped.

A room that matches nothing is *unzoned*, not dropped. Named labs are real rooms
with real classes in them, and losing them from the checking list would be a
silent monitoring gap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: "KT-318(A)" -> ("KT", "318"). The building may carry a digit of its own
#: (ANX1, G1), so the split is on the hyphen, not on the first digit.
_ROOM_RE = re.compile(r"^\s*([A-Z]+\d*)\s*-\s*(\d+)", re.IGNORECASE)

#: The key used for an unmatched room, so it can still be assigned to staff.
UNZONED = "UNZONED"


@dataclass(frozen=True, slots=True)
class Zone:
    key: str
    building: str
    floor: int | None

    @property
    def label(self) -> str:
        if self.floor is None:
            return "Other rooms"
        if self.floor == 0:
            return f"{self.building} · Ground floor"
        return f"{self.building} · Floor {self.floor}"

    @property
    def short_label(self) -> str:
        if self.floor is None:
            return "Other"
        return f"{self.building}-{self.floor}"


UNZONED_ZONE = Zone(key=UNZONED, building="", floor=None)


def room_zone(room: str) -> Zone:
    """The zone a room belongs to. Never raises; unknown shapes are UNZONED."""
    if not room:
        return UNZONED_ZONE
    match = _ROOM_RE.match(room)
    if not match:
        return UNZONED_ZONE

    building = match.group(1).upper()
    number = match.group(2)
    # The leading digit is the floor: 318 -> 3, 001 -> 0, 04 -> 0.
    floor = int(number[0])
    return Zone(key=f"{building}-{floor}", building=building, floor=floor)


def zone_key(room: str) -> str:
    return room_zone(room).key


def zones_for_rooms(rooms: list[str]) -> list[dict[str, object]]:
    """Summarise the zones a set of rooms spans, with a room count each.

    Sorted by building then floor so the admin screen reads like a directory.
    """
    buckets: dict[str, dict[str, object]] = {}
    for room in rooms:
        zone = room_zone(room)
        entry = buckets.setdefault(
            zone.key,
            {
                "key": zone.key,
                "building": zone.building,
                "floor": zone.floor,
                "label": zone.label,
                "short_label": zone.short_label,
                "rooms": [],
            },
        )
        rooms_list = entry["rooms"]
        assert isinstance(rooms_list, list)
        if room not in rooms_list:
            rooms_list.append(room)

    for entry in buckets.values():
        rooms_list = entry["rooms"]
        assert isinstance(rooms_list, list)
        rooms_list.sort()
        entry["room_count"] = len(rooms_list)

    return sorted(
        buckets.values(),
        # Unzoned sinks to the bottom; it is a catch-all, not a place.
        key=lambda e: (e["floor"] is None, str(e["building"]), e["floor"] or 0),
    )
