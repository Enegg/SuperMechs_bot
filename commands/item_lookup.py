from __future__ import annotations

import logging
import typing as t
from itertools import zip_longest
from operator import sub

from disnake import ButtonStyle, CommandInteraction, Embed, MessageInteraction
from disnake.ext import commands
from typing_extensions import Self

from config import TEST_GUILDS
from SuperMechs.core import MAX_BUFFS, STATS, Stat
from SuperMechs.item import AnyItem
from SuperMechs.types import AnyStats
from ui.buttons import Button, ToggleButton, button
from ui.views import InteractionCheck, SaneView, positioned
from utils import dict_items_as, search_for

if t.TYPE_CHECKING:
    from bot import SMBot

T = t.TypeVar("T")

logger = logging.getLogger(f"main.{__name__}")


class ItemView(InteractionCheck, SaneView):
    def __init__(
        self,
        embed: Embed,
        item: AnyItem,
        callback: t.Callable[[Embed, AnyItem, bool, bool], None],
        *,
        user_id: int,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.call = callback
        self.embed = embed
        self.item = item

        if not {"phyDmg", "eleDmg", "ExpDmg"} & set(item.stats):
            self.remove_item(self.avg_button, 0)

        callback(embed, item, False, False)

    @positioned(0, 0)
    @button(cls=ToggleButton, label="Buffs", custom_id="button:buffs")
    async def buff_button(self, button: ToggleButton, inter: MessageInteraction) -> None:
        button.toggle()
        self.embed.clear_fields()
        self.call(self.embed, self.item, button.on, self.avg_button.on)
        await inter.response.defer()
        await inter.edit_original_message(embed=self.embed, view=self)

    @positioned(0, 1)
    @button(cls=ToggleButton, label="Show damage spread", custom_id="button:dmg")
    async def avg_button(self, button: ToggleButton, inter: MessageInteraction) -> None:
        button.toggle()
        self.embed.clear_fields()
        self.call(self.embed, self.item, self.buff_button.on, button.on)
        await inter.response.defer()
        await inter.edit_original_message(embed=self.embed, view=self)

    @positioned(0, 2)
    @button(label="Quit", style=ButtonStyle.red, custom_id="button:quit")
    async def quit_button(self, _: Button[Self], inter: MessageInteraction) -> None:
        self.stop()
        await inter.response.defer()


class ItemCompareView(InteractionCheck, SaneView):
    def __init__(
        self,
        embed: Embed,
        item_a: AnyItem,
        item_b: AnyItem,
        *,
        user_id: int,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.embed = embed
        self.item_a = item_a
        self.item_b = item_b

        self.prepare()

    @positioned(0, 0)
    @button(cls=ToggleButton, label="Arena buffs", custom_id="button:buffs")
    async def buffs_button(self, button: ToggleButton, inter: MessageInteraction) -> None:
        button.toggle()
        self.prepare()
        await inter.response.edit_message(embed=self.embed, view=self)

    @positioned(0, 1)
    @button(label="Quit", style=ButtonStyle.red, custom_id="button:quit")
    async def quit_button(self, button: Button[Self], inter: MessageInteraction) -> None:
        await inter.response.defer()
        self.stop()

    def prepare(self) -> None:
        name_field, first_field, second_field = stats_to_fields(
            MAX_BUFFS.buff_stats(self.item_a.stats) if self.buffs_button.on else self.item_a.stats,
            MAX_BUFFS.buff_stats(self.item_b.stats) if self.buffs_button.on else self.item_b.stats,
        )
        if self.item_a.tags.require_jump:
            first_field.append("❕")

        if self.item_b.tags.require_jump:
            second_field.append("❕")

        if self.item_a.tags.require_jump or self.item_b.tags.require_jump:
            name_field.append(f"{STATS['jump'].emoji} **Jumping required**")

        if len(self.embed.fields):
            modify = self.embed.set_field_at

        else:
            modify = self.embed.insert_field_at

        modify(0, "Stat", "\n".join(name_field))
        modify(1, try_shorten(self.item_a.name), "\n".join(first_field))
        modify(2, try_shorten(self.item_b.name), "\n".join(second_field))


class ItemLookup(commands.Cog):
    def __init__(self, bot: SMBot) -> None:
        self.bot = bot

    @commands.slash_command()
    async def item(
        self,
        inter: CommandInteraction,
        name: str,
        compact: bool = False,
        invisible: bool = True,
    ) -> None:
        """Finds an item and returns its stats {{ ITEM }}

        Parameters
        -----------
        name: The name of the item or an abbreviation of it {{ ITEM_NAME }}
        compact: Whether the embed sent back should be compact (breaks on mobile) {{ ITEM_COMPACT }}
        invisible: Whether the bot response is visible only to you {{ ITEM_VISIBILITY }}
        """

        if name not in self.bot.items_cache:
            if name == "Start typing to get suggestions...":
                raise commands.UserInputError("This is only an information and not an option")

            raise commands.UserInputError("Item not found.")

        item = self.bot.items_cache[name]

        if compact:
            embed = (
                Embed(color=item.element.color)
                .set_author(name=item.name, icon_url=item.type.image_url)
                .set_thumbnail(url=item.image_url)
            )
            embed_preset = compact_embed

        else:
            embed = (
                Embed(
                    title=item.name,
                    description=f"{item.element.name.capitalize()} "
                    f"{item.type.name.replace('_', ' ').lower()}",
                    color=item.element.color,
                )
                .set_thumbnail(url=item.type.image_url)
                .set_image(url=item.image_url)
            )
            embed_preset = default_embed

        view = ItemView(embed, item, embed_preset, user_id=inter.author.id)
        await inter.send(embed=embed, view=view, ephemeral=invisible)

        await view.wait()
        await inter.edit_original_message(view=None)

    @commands.slash_command(guild_ids=TEST_GUILDS)
    async def item_raw(self, inter: CommandInteraction, name: str) -> None:
        """Finds an item and returns its raw stats {{ ITEM }}

        Parameters
        -----------
        name: The name of the item or an abbreviation of it {{ ITEM_NAME }}
        """

        if name not in self.bot.items_cache:
            if name == "Start typing to get suggestions...":
                raise commands.UserInputError("This is only an information and not an option")

            raise commands.UserInputError("Item not found.")

        item = self.bot.items_cache[name]

        await inter.send(f"`{item!r}`", ephemeral=True)

    @commands.slash_command()
    async def compare(self, inter: CommandInteraction, item1: str, item2: str) -> None:
        """Shows an interactive comparison of two items. {{ COMPARE }}

        Parameters
        -----------
        item1: First item to compare. {{ COMPARE_FIRST }}
        item2: Second item to compare. {{ COMPARE_SECOND }}
        """
        item_a = self.bot.items_cache.get(item1)
        item_b = self.bot.items_cache.get(item2)

        if item_a is None or item_b is None:
            raise commands.UserInputError("Either of specified items not found.")

        if item_a.type is item_b.type and item_a.element is item_b.element:
            desc = (
                f"{item_a.element.name.capitalize()} {item_a.type.name.replace('_', ' ').lower()}"
            )

            if not desc.endswith("s"):
                desc += "s"

        else:
            desc = (
                f"{item_a.element.name.capitalize()} "
                f"{item_a.type.name.replace('_', ' ').lower()}"
                " | "
                f"{item_b.element.name.capitalize()} "
                f"{item_b.type.name.replace('_', ' ').lower()}"
            )

        embed = Embed(
            title=f"{item_a.name} vs {item_b.name}",
            description=desc,
            color=item_a.element.color if item_a.element is item_b.element else inter.author.color,
        )

        view = ItemCompareView(embed, item_a, item_b, user_id=inter.author.id)
        await inter.send(embed=embed, view=view, ephemeral=True)

        await view.wait()
        await inter.edit_original_message(view=None)

    @item.autocomplete("name")
    @item_raw.autocomplete("name")
    @compare.autocomplete("item1")
    @compare.autocomplete("item2")
    async def item_autocomplete(self, inter: CommandInteraction, input: str) -> list[str]:
        """Autocomplete for items"""
        if len(input) < 2:
            return ["Start typing to get suggestions..."]

        items = sorted(
            set(search_for(input, self.bot.items_cache))
            | self.bot.item_abbrevs.get(input.lower(), set())
        )

        if len(items) <= 25:
            return items

        return items[:25]


def avg_and_deviation(a: int | tuple[int, int], b: int | None = None) -> tuple[float, float]:
    if isinstance(a, tuple):
        a, b = a

    elif b is None:
        raise ValueError("Got a single argument which is not a tuple")

    avg = (a + b) / 2
    deviation = (b - avg) / avg
    return avg, deviation


def buffed_stats(
    item: AnyItem, buffs_enabled: bool
) -> t.Iterator[tuple[str, tuple[int, int] | tuple[tuple[int, int], tuple[int, int]]]]:
    apply_buff = MAX_BUFFS.total_buff_difference if buffs_enabled else lambda _, value: (value, 0)

    for stat, value in dict_items_as(int | list[int], item.stats):
        if stat == "health":
            assert type(value) is int
            yield stat, (value, 0)
            continue

        match value:
            case int():
                yield stat, apply_buff(stat, value)

            case [int() as x, y] if x == y:
                yield stat, apply_buff(stat, x)

            case [x, y]:
                yield stat, (apply_buff(stat, x), apply_buff(stat, y))


def default_embed(embed: Embed, item: AnyItem, buffs_enabled: bool, avg: bool) -> None:
    """Fills embed with full-featured info about an item."""

    if item.rarity.is_single:
        transform_range = f"({item.rarity})"

    else:
        tiers = [tier.emoji for tier in item.rarity]
        tiers[-1] = f"({tiers[-1]})"
        transform_range = "".join(tiers)

    embed.add_field(name="Transform range: ", value=transform_range, inline=False)

    spaced = False
    item_stats = ""  # the main string
    cost_stats = {"backfire", "heaCost", "eneCost"}

    for stat, (value, diff) in buffed_stats(item, buffs_enabled):
        if not spaced and stat in cost_stats:
            item_stats += "\n"
            spaced = True

        if not (isinstance(value, tuple) and isinstance(diff, tuple)):
            text = str(value)
            change = f" **{diff:+}**" if diff else ""

        elif avg and stat != "range":
            v1, d1 = value
            v2, d2 = diff

            avg_dmg, dev = avg_and_deviation(v1, v2)
            avg_diff = (d1 + d2) / 2

            text = f"{avg_dmg:g} ±{dev:.1%}"
            change = f" **{avg_diff:+g}**" if avg_diff else ""

        else:
            v1, d1 = value
            v2, d2 = diff

            text = f"{v1}-{v2}"
            change = f" **{d1:+} {d2:+}**" if d1 or d2 else ""

        name = STATS[stat].name

        if stat == "uses":
            name = "Use" if value == 1 else "Uses"

        item_stats += f"{STATS[stat].emoji} **{text}** {name}{change}\n"

    if item.tags.require_jump:
        item_stats += f"{STATS['jump'].emoji} **Jumping required**"

    embed.add_field(name="Stats:", value=item_stats, inline=False)


def compact_embed(embed: Embed, item: AnyItem, buffs_enabled: bool, avg: bool) -> None:
    """Fills embed with reduced in size item info."""

    if item.rarity.is_single:
        transform_range = f"({item.rarity})"

    else:
        tiers = [tier.emoji for tier in item.rarity]
        tiers[-1] = f"({tiers[-1]})"
        transform_range = "".join(tiers)

    lines: list[str] = []

    for stat, (value, diff) in buffed_stats(item, buffs_enabled):
        if not (isinstance(value, tuple) and isinstance(diff, tuple)):
            text = str(value)

        elif avg and stat != "range":
            a, b = avg_and_deviation(value[0], diff[0])
            text = f"{a:g} ±{b:.1%}"

        else:
            text = f"{value[0]}-{diff[0]}"

        lines.append(f"{STATS[stat].emoji} **{text}**")

    if item.tags.require_jump:
        lines.append(f"{STATS['jump'].emoji}❗")

    line_count = len(lines)

    if line_count > 4 and not 0 != line_count % 4 < 3:  # == 0 or > 2
        div = 4

    elif not 0 != line_count % 3 < 2:  # == 0 or > 1
        div = 3

    elif line_count < 4:
        div = 2

    else:
        div = 4

    field_text = ("\n".join(lines[i : i + div]) for i in range(0, line_count, div))

    for name, field in zip_longest((transform_range,), field_text, fillvalue="⠀"):
        embed.add_field(name=name, value=field)


tuple_of_tuples = tuple[tuple[T, T], tuple[T, T]]


@t.overload
def cmp_num(x: int, y: int, lower_is_better: bool = False) -> tuple_of_tuples[int]:
    ...


@t.overload
def cmp_num(x: float, y: float, lower_is_better: bool = False) -> tuple_of_tuples[float]:
    ...


def cmp_num(x: float, y: float, lower_is_better: bool = False) -> tuple_of_tuples[float]:
    if x == y:
        return ((x, 0), (y, 0))

    return ((x, x - y), (y, 0)) if lower_is_better ^ (x > y) else ((x, 0), (y, y - x))


value_and_diff = tuple[int | float | None, float]


class ValueRuleSet(t.NamedTuple):
    comparator: t.Callable[[int, int], tuple[int | float, bool | None]]
    format_value: t.Callable[[int], str]
    format_diff: t.Callable[[float], str] = lambda d: f"{d:+g}"


class RangeRuleSet(t.NamedTuple):
    comparator: t.Callable[[list[int], list[int]], tuple[int | float, bool | None]]
    format_value: t.Callable[[list[int]], str]
    format_diff: t.Callable[[float], str] = lambda d: f"{d:+g}"


rulesets: dict[str, ValueRuleSet | RangeRuleSet] = {
    "range": RangeRuleSet(
        lambda a, b: (abs(sub(*a) - sub(*b)), None), lambda v: "-".join(map(str, v))
    ),
}

# TODO: generic comparator for N items, with rulesets
# add intermediary iterator which will create extra fields like the damage spread %


def ruleset_comparator(stats_a: AnyStats, stats_b: AnyStats):
    for stat_name, stat in STATS.items():
        stat_a: int | list[int] | None = stats_a.get(stat_name)
        stat_b: int | list[int] | None = stats_b.get(stat_name)

        if stat_a is stat_b is None:
            continue

        rulesets.get(stat_name)


def comparator(
    stats_a: AnyStats, stats_b: AnyStats
) -> t.Iterator[
    tuple[
        str,
        Stat,
        tuple[value_and_diff, value_and_diff]
        | tuple[value_and_diff, value_and_diff, value_and_diff, value_and_diff],
    ]
]:
    undesired = {"weight", "backfire", "heaCost", "eneCost"}
    special_cases = {"range"}

    for stat_name, stat in STATS.items():
        stat_a: int | list[int] | None = stats_a.get(stat_name)
        stat_b: int | list[int] | None = stats_b.get(stat_name)

        if stat_name in special_cases and not (stat_a is stat_b is None):
            yield stat_name, stat, (
                tuple(stat_a) if isinstance(stat_a, list) else (None, 0),
                tuple(stat_b) if isinstance(stat_b, list) else (None, 0),
            )
            continue

        match stat_a, stat_b:
            case (None, None):
                continue

            case (int() as a, int() as b):
                yield stat_name, stat, cmp_num(a, b, stat_name in undesired)
                continue

            case ([int() as a1, int() as a2], [int() as b1, int() as b2]):
                x_avg, x_inacc = avg_and_deviation(a1, a2)
                y_avg, y_inacc = avg_and_deviation(b1, b2)

                yield stat_name, stat, cmp_num(x_avg, y_avg, False) + cmp_num(
                    x_inacc, y_inacc, True
                )
                continue

        if isinstance(stat_a, int):
            yield stat_name, stat, ((stat_a, 0), (None, 0))

        elif isinstance(stat_b, int):
            yield stat_name, stat, ((None, 0), (stat_b, 0))

        elif stat_a is not None:
            avg, inacc = avg_and_deviation(*stat_a)
            yield stat_name, stat, ((avg, 0), (None, 0), (inacc, 0), (None, 0))

        elif stat_b is not None:
            avg, inacc = avg_and_deviation(*stat_b)
            yield stat_name, stat, ((None, 0), (avg, 0), (None, 0), (inacc, 0))


def stats_to_fields(stats_a: AnyStats, stats_b: AnyStats) -> tuple[list[str], list[str], list[str]]:
    name_field: list[str] = []
    first_item: list[str] = []
    second_item: list[str] = []

    for stat_name, stat, long_boy in comparator(stats_a, stats_b):
        name_field.append(f"{stat.emoji} {stat.name}")

        match (stat_name, long_boy):
            case ("range", ((a1, a2), (b1, b2))):
                first_item.append(f"**{a1}-{a2}**" if a1 is not None else "")
                second_item.append(f"**{b1}-{b2}**" if b1 is not None else "")

            case (_, ((_, _), (_, _)) as tup):
                for (value, diff), field in zip(tup, (first_item, second_item)):
                    if value is None:
                        string = ""

                    elif diff == 0:
                        string = f"**{value:g}**"

                    else:
                        string = f"**{value:g}** {diff:+g}"

                    field.append(string)

            case (_, ((_, _), (_, _), (_, _), (_, _)) as tup):
                name_field.append("🎲 Damage spread")

                for (avg, diff), (spread, s_diff), field in zip(
                    tup[:2], tup[2:], (first_item, second_item)
                ):
                    if avg is None:
                        string = ""

                    elif diff == 0:
                        string = f"**{avg:g}**"

                    else:
                        string = f"**{avg:g}** {diff:+g}"

                    field.append(string)

                    if spread is None:
                        string = ""

                    elif s_diff == 0:
                        string = f"**{spread:.1%}**"

                    else:
                        string = f"**{spread:.1%}** {s_diff:+.1%}"

                    field.append(string)

    return name_field, first_item, second_item


def try_shorten(name: str) -> str:
    if len(name) < 16:
        return name

    return "".join(s for s in name if s.isupper())


def setup(bot: SMBot) -> None:
    bot.add_cog(ItemLookup(bot))
    logger.info('Cog "ItemLookupCog" loaded')
