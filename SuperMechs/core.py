from __future__ import annotations

import typing as t


class GameVars(t.NamedTuple):
    MAX_WEIGHT: int = 1000
    OVERWEIGHT: int = 10
    PENALTIES: dict[str, int] = {"health": 15}

    @property
    def MAX_OVERWEIGHT(self) -> int:
        return self.MAX_WEIGHT + self.OVERWEIGHT


DEFAULT_VARS = GameVars()


class ArenaBuffs:
    ref_def = (0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 20)
    ref_hp = (0, +10, +30, +60, 90, 120, 150, 180, +220, +260, 300, 350)
    stat_ref = ("eneCap", "eneReg", "eneDmg", "heaCap", "heaCol", "heaDmg", "phyDmg",
                "expDmg", "eleDmg", "phyRes", "expRes", "eleRes", "health", "backfire")

    def __init__(self, levels: dict[str, int] | None = None) -> None:
        self.levels = levels or dict.fromkeys(self.stat_ref, 0)

    def __getitem__(self, key: str) -> int:
        return self.levels[key]

    def __repr__(self) -> str:
        return f"<{type(self).__name__} " + \
            ", ".join(f"{stat}={lvl}" for stat, lvl in self.levels.items()) + ">"

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
            return value + self.ref_hp[level]

        return round(value * (1 + self.get_percent(stat, level) / 100))

    def total_buff_difference(self, stat: str, value: int) -> tuple[int, int]:
        """Buffs a value and returns the total as well as
        the difference between the total and initial value."""
        buffed = self.total_buff(stat, value)
        return buffed, buffed - value

    @classmethod
    def get_percent(cls, stat: str, level: int) -> int:
        match stat:
            case "health":
                raise TypeError('"Health" stat has absolute increase, not percent')

            case "backfire":
                return -cls.ref_def[level]

            case "expRes" | "eleRes" | "phyRes":
                return cls.ref_def[level] * 2

            case _:
                return cls.ref_def[level]

    @classmethod
    def buff_as_str(cls, stat: str, level: int) -> str:
        if stat == "health":
            return f"+{cls.ref_hp[level]}"

        return f"{cls.get_percent(stat, level):+}%"

    def buff_as_str_aware(self, stat: str) -> str:
        return self.buff_as_str(stat, self.levels[stat])

    @classmethod
    def iter_as_str(cls, stat: str) -> t.Iterator[str]:
        levels = len(cls.ref_hp) if stat == "health" else len(cls.ref_def)

        for n in range(levels):
            yield cls.buff_as_str(stat, n)

    @classmethod
    def maxed(cls) -> ArenaBuffs:
        self = cls.__new__(cls)

        self.levels = dict.fromkeys(cls.stat_ref, len(cls.ref_def)-1)
        self.levels["health"] = len(cls.ref_hp) - 1

        return self


MAX_BUFFS = ArenaBuffs.maxed()