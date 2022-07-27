from __future__ import annotations

import typing as t
from collections import defaultdict
from difflib import SequenceMatcher
from heapq import nlargest
from json import load

from typing_extensions import Self

from utils import MISSING, dict_items_as

from .types import AnyMechStats, AnyStatKey, AnyStats, StatDict

# order reference
WORKSHOP_STATS: t.Final = (
    "weight",
    "health",
    "eneCap",
    "eneReg",
    "heaCap",
    "heaCol",
    "phyRes",
    "expRes",
    "eleRes",
    "bulletCap",
    "rocketCap",
    "walk",
    "jump",
)


class Name(t.NamedTuple):
    default: str
    in_game: str = MISSING
    short: str = MISSING

    def __str__(self) -> str:
        return self.default

    def __format__(self, __format_spec: str, /) -> str:
        return self.default.__format__(__format_spec)

    @property
    def game_name(self) -> str:
        return self.default if self.in_game is MISSING else self.in_game

    @property
    def short_name(self) -> str:
        if self.short is not MISSING:
            return self.short

        return self.default if len(self.default) <= len(self.game_name) else self.game_name


class Stat(t.NamedTuple):
    name: Name
    emoji: str = "❔"
    beneficial: bool = True
    buff: tuple[str, int] | None = None

    @classmethod
    def from_dict(cls, json: StatDict) -> Self:
        buff = json.get("buff", None)
        new = {
            "name": Name(**json["names"]),
            "beneficial": "beneficial" not in json,
            "buff": None if buff is None else (buff["mode"], buff["range"]),
        }
        if emoji := json.get("emoji"):
            new["emoji"] = emoji

        return cls(**new)


with open("SuperMechs/GameData/StatData.json") as file:
    json: dict[AnyStatKey, StatDict] = load(file)

    STATS = {stat_key: Stat.from_dict(value) for stat_key, value in json.items()}


class GameVars(t.NamedTuple):
    MAX_WEIGHT: int = 1000
    OVERWEIGHT: int = 10
    PENALTIES: AnyMechStats = { "health": 15 }

    @property
    def MAX_OVERWEIGHT(self) -> int:
        return self.MAX_WEIGHT + self.OVERWEIGHT

    @staticmethod
    def default() -> GameVars:
        return DEFAULT_VARS


DEFAULT_VARS = GameVars()


class ArenaBuffs:
    # fmt: off
    BASE_PERCENT = (0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 20)
    HP_INCREASES = (0, +10, +30, +60, 90, 120, 150, 180, +220, +260, 300, 350)
    STATS_REFERENCE = (
        "eneCap", "eneReg", "eneDmg", "heaCap", "heaCol", "heaDmg", "phyDmg",
        "expDmg", "eleDmg", "phyRes", "expRes", "eleRes", "health", "backfire"
    )
    # fmt: on

    def __init__(self, levels: dict[str, int] | None = None) -> None:
        self.levels = levels or dict.fromkeys(self.STATS_REFERENCE, 0)

        self.__getitem__ = self.levels.__getitem__

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            + ", ".join(f"{stat}={lvl}" for stat, lvl in self.levels.items())
            + f" at 0x{id(self):016X}>"
        )

    @property
    def is_at_zero(self) -> bool:
        """Whether all buffs are at level 0"""
        return all(v == 0 for v in self.levels.values())

    def total_buff(self, stat: str, value: int) -> int:
        """Buffs a value according to given stat."""
        if stat not in self.levels:
            return value

        level = self.levels[stat]

        if stat == "health":
            return value + self.HP_INCREASES[level]

        return round(value * (1 + self.get_percent(stat, level) / 100))

    def total_buff_difference(self, stat: str, value: int) -> tuple[int, int]:
        """Buffs a value and returns the total as well as
        the difference between the total and initial value."""
        buffed = self.total_buff(stat, value)
        return buffed, buffed - value

    @classmethod
    def get_percent(cls, stat_name: str, level: int) -> int:
        """Returns an int representing the precentage for the stat's increase."""
        match stat_name:
            case "health":
                raise TypeError('"Health" stat has absolute increase, not percent')

            case "backfire":
                return -cls.BASE_PERCENT[level]

            case "expRes" | "eleRes" | "phyRes":
                return cls.BASE_PERCENT[level] * 2

            case _:
                return cls.BASE_PERCENT[level]

    @classmethod
    def buff_as_str(cls, stat_name: str, level: int) -> str:
        """Returns a formatted string representation of the stat's value at the given level."""
        if stat_name == "health":
            return f"+{cls.HP_INCREASES[level]}"

        return f"{cls.get_percent(stat_name, level):+}%"

    def buff_as_str_aware(self, stat: str) -> str:
        """Returns a formatted string representation of the stat's value."""
        return self.buff_as_str(stat, self.levels[stat])

    @classmethod
    def iter_as_str(cls, stat_name: str) -> t.Iterator[str]:
        levels = len(cls.HP_INCREASES) if stat_name == "health" else len(cls.BASE_PERCENT)

        for n in range(levels):
            yield cls.buff_as_str(stat_name, n)

    @classmethod
    def maxed(cls) -> ArenaBuffs:
        """Returns an ArenaBuffs object with all levels maxed."""

        levels = dict.fromkeys(cls.STATS_REFERENCE, len(cls.BASE_PERCENT) - 1)
        levels["health"] = len(cls.HP_INCREASES) - 1
        max_buffs = cls(levels)

        setattr(cls, "maxed", staticmethod(lambda: max_buffs))

        return max_buffs

    def buff_stats(self, stats: AnyStats, /, *, buff_health: bool = False) -> AnyStats:
        """Returns the buffed stats."""
        buffed: AnyStats = {}

        for key, value in dict_items_as(int | list[int], stats):
            if key == "health" and not buff_health:
                assert type(value) is int
                buffed[key] = value

            elif isinstance(value, list):
                buffed[key] = [self.total_buff(key, v) for v in value]

            else:
                value = self.total_buff(key, value)
                buffed[key] = value

        return buffed


MAX_BUFFS = ArenaBuffs.maxed()


def abbreviate_name(name: str, /) -> str | None:
    """Create an abbreviation from a single name. The abbreviation is simply
    made of all uppercase letters that occur in the name, unless
    there are no lowercase letters or it tests True for .istitle."""
    if name.isupper() or (" " not in name and name.istitle()):
        return None

    # Hybrid Heat Cannon => hhc, HeronMark => hm
    return "".join(a.lower() for a in name if a.isupper())


def abbreviate_names_2(names: t.Iterable[str], /) -> dict[str, set[str]]:
    """Returns dict of abbreviations:
    Energy Free Armor => EFA"""
    abbrevs: defaultdict[str, set[str]] = defaultdict(set)

    for name in names:
        if (abbrev := abbreviate_name(name)) is not None:
            abbrevs[abbrev].add(name)

    return abbrevs


def abbreviate_names(names: t.Iterable[str], /) -> dict[str, set[str]]:
    """Returns dict of abbreviations:
    Energy Free Armor => EFA"""
    abbrevs: dict[str, set[str]] = {}

    for name in names:
        # skip items like EMP or Flaminator, there's no short name for that
        if (abb := abbreviate_name(name)) is None:
            continue

        abbrev = {abb}

        if " " in name:
            # merge multi-word names into one, people mistake that often enough
            abbrev.add(name.replace(" ", "").lower())

        elif not name.istitle():
            # HeronMark => heron, mark
            last = 0
            for i, a in enumerate(name):
                if a.isupper():
                    if string := name[last:i].lower():
                        abbrev.add(string)

                    last = i

            abbrev.add(name[last:].lower())

        # one abbreviation can match multiple items
        for abb in abbrev:
            abbrevs.setdefault(abb, {name}).add(name)

    return abbrevs


VT = t.TypeVar("VT")


def get_matching_items(
    mapping: t.Mapping[str, VT], name: str, abbrevs: dict[str, set[str]], /, *, limit: int = 25
) -> list[VT]:
    """Return a list of items which closely match the name and/or abbreviation."""

    name = name.lower()

    if (item_names := abbrevs.get(name)) is not None:
        # it is quite implausible for the number of abbreviations to surpass the default 25.
        # However, it is possible in case a low limit is passed and/or when dealing with custom items,
        # in which case it is ambiguous what to do with the abbreviations,
        # hence we raise ValueError instead of silently slicing.
        if len(item_names) > limit:
            raise ValueError("Found more abbreviations than the limit allows")

        items = [mapping[name] for name in item_names]

    else:
        items: list[VT] = []

    # this part is similar to difflib.get_close_matches implementation,
    # but since we want to support matching partial names like "Can" in "Hybrid Heat Cannon",
    # we create own algorithm
    cutoff = 0.6
    matched: list[tuple[float, VT]] = []
    matcher = SequenceMatcher(lambda x: x == " ")
    matcher.set_seq2(name)

    def predicate() -> bool:
        return (
            matcher.real_quick_ratio() >= cutoff
            and matcher.quick_ratio() >= cutoff
            and matcher.ratio() >= cutoff
        )

    for item_name in mapping:
        matcher.set_seq1(item_name.lower())

        if predicate():
            matched.append((matcher.ratio(), mapping[item_name]))

        elif " " in item_name:
            parts = item_name.split()

    if matched:
        # abbreviations first, then matches sorted by similarity
        items.extend(item for _, item in nlargest(limit - len(items), matched, key=lambda i: i[0]))

    return items
