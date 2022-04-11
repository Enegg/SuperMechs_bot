from __future__ import annotations

import typing as t
from itertools import zip_longest

import disnake
import lib_types
from config import TEST_GUILDS
from disnake import ButtonStyle
from disnake.ext import commands
from SuperMechs.enums import STAT_NAMES
from SuperMechs.item import AnyItem
from SuperMechs.sm_base import MAX_BUFFS
from SuperMechs.types import AnyStats
from typing_extensions import Self
from ui.buttons import Button, ToggleButton, button
from ui.views import PersonalView
from utils import search_for

if t.TYPE_CHECKING:
    from bot import SMBot


class ItemView(PersonalView):
    def __init__(
        self,
        embed: disnake.Embed,
        item: AnyItem,
        callback: t.Callable[[disnake.Embed, AnyItem, bool, bool], None],
        *,
        user_id: int,
        timeout: float | None = 180
    ) -> None:
        super().__init__(user_id=user_id, timeout=timeout)
        self.call = callback
        self.embed = embed
        self.item = item

        callback(embed, item, False, False)

    @button(cls=ToggleButton[Self], label="Buffs")
    async def buff_button(
        self, button: ToggleButton[Self], inter: disnake.MessageInteraction
    ) -> None:
        button.toggle()
        self.embed.clear_fields()
        self.call(self.embed, self.item, button.on, self.avg_button.on)
        await inter.response.defer()
        await inter.edit_original_message(embed=self.embed, view=self)

    @button(cls=ToggleButton[Self], label="Show damage spread")
    async def avg_button(
        self, button: ToggleButton[Self], inter: disnake.MessageInteraction
    ) -> None:
        button.toggle()
        self.embed.clear_fields()
        self.call(self.embed, self.item, self.buff_button.on, button.on)
        await inter.response.defer()
        await inter.edit_original_message(embed=self.embed, view=self)

    @button(label="Quit", style=disnake.ButtonStyle.red)
    async def quit_button(self, _: Button[Self], inter: disnake.MessageInteraction) -> None:
        self.stop()
        await inter.response.defer()


class CompareView(PersonalView):
    def __init__(
        self,
        embed: disnake.Embed,
        item_a: AnyItem,
        item_b: AnyItem,
        *,
        user_id: int,
        timeout: float | None = 180
    ) -> None:
        super().__init__(user_id=user_id, timeout=timeout)
        self.embed = embed
        self.item_a = item_a
        self.item_b = item_b

    @button(label="Buffs A")
    async def buff_button_A(self, button: Button[Self], inter: disnake.MessageInteraction) -> None:
        if was_off := button.style is ButtonStyle.gray:
            button.style = ButtonStyle.green

        else:
            button.style = ButtonStyle.gray

        await inter.response.edit_message(view=self)


def buff(stat: str, enabled: bool, value: int) -> int:
    """Returns a value buffed respectively to stat type"""
    if not enabled or stat == "health":
        return value

    return MAX_BUFFS.total_buff(stat, value)


def buff_difference(stat: str, enabled: bool, value: int) -> tuple[int, int]:
    """Returns a value buffed respectively to stat type and the difference between it and base"""
    if not enabled or stat == "health":
        return value, 0

    return MAX_BUFFS.total_buff_difference(stat, value)


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
    m_buff = MAX_BUFFS.total_buff_difference if buffs_enabled else lambda _, value: (value, 0)

    for stat, value in item.stats.items():
        if stat == "health":
            yield stat, (t.cast(int, value), 0)
            continue

        match value:
            case int():
                yield stat, m_buff(stat, value)

            case [int() as x, y] if x == y:
                yield stat, m_buff(stat, x)

            case [int() as x, int() as y]:
                yield stat, (m_buff(stat, x), m_buff(stat, y))


def default_embed(embed: disnake.Embed, item: AnyItem, buffs_enabled: bool, avg: bool) -> None:
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

        name, emoji = STAT_NAMES[stat]

        if stat == "uses":
            name = "Use" if value == 1 else "Uses"

        item_stats += f"{emoji} **{text}** {name}{change}\n"

    if "advance" in item.stats or "retreat" in item.stats:
        item_stats += f"{STAT_NAMES['jump'].emoji} **Jumping required**"

    embed.add_field(name="Stats:", value=item_stats, inline=False)


def compact_embed(embed: disnake.Embed, item: AnyItem, buffs_enabled: bool, avg: bool) -> None:
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

        lines.append(f"{STAT_NAMES[stat].emoji} **{text}**")

    if "advance" in item.stats or "retreat" in item.stats:
        lines.append(f"{STAT_NAMES['jump'].emoji}❗")

    line_count = len(lines)

    if line_count > 4 and not 0 != line_count % 4 < 3:  # == 0 or > 2
        div = 4

    elif not 0 != line_count % 3 < 2:  # == 0 or > 1
        div = 3

    elif line_count < 4:
        div = 2

    else:
        div = 4

    field_text = ("\n".join(lines[i:i+div]) for i in range(0, line_count, div))
    name_field_zip = zip_longest((transform_range,), field_text, fillvalue="⠀")

    for name, field in name_field_zip:
        embed.add_field(name=name, value=field)


@commands.slash_command()
async def item(
    inter: lib_types.ApplicationCommandInteraction,
    name: str,
    compact: bool = False,
    invisible: bool = True,
    raw: bool = False
) -> None:
    """Finds an item and returns its stats

    Parameters
    -----------
    name: The name of the item or an abbreviation of it
    compact: Whether the embed sent back should be compact (breaks on mobile)
    invisible: Whether the bot response is visible only to you
    raw: Whether not to format the embed and send raw data instead
    """

    if name not in inter.bot.items_cache:
        raise commands.UserInputError("Item not found.")

    item = inter.bot.items_cache[name]

    # debug flag
    if raw:
        await inter.send(f"`{item!r}`", ephemeral=invisible)
        return

    if compact:
        embed = (disnake.Embed(
            color=item.element.color)
            .set_author(name=item.name, icon_url=item.icon.URL)
            .set_thumbnail(url=item.image_url))
        view = ItemView(embed, item, compact_embed, user_id=inter.author.id)

    else:
        embed = (disnake.Embed(
            title=item.name,
            description=f"{item.element.name.capitalize()} "
                        f"{item.type.replace('_', ' ').lower()}",
            color=item.element.color)
            .set_thumbnail(url=item.icon.URL)
            .set_image(url=item.image_url))
        view = ItemView(embed, item, default_embed, user_id=inter.author.id)

    await inter.send(embed=embed, view=view, ephemeral=invisible)
    await view.wait()
    await inter.edit_original_message(view=None)


def cmp_two(a: object, b: object, lower_is_better: bool = False):
    match a, b:
        case int() as x, int() as y:
            if x < y:
                diff = y - x

                if lower_is_better:
                    return (-diff, "x")

                else:
                    return (diff, "y")

            elif x > y:
                diff = x - y

                if lower_is_better:
                    return (-diff, "y")

                else:
                    return (diff, "x")

            else:
                return (0, "neither")

        case ([int() as x1, int() as x2], [int() as y1, int() as y2]):
            x = avg_and_deviation(x1, x2)
            y = avg_and_deviation(y1, y2)

            if x > y:
                pass

            elif x < y:
                pass

            else:
                pass


def compare_stats(a: AnyStats, b: AnyStats):
    out = {}

    lower_is_better = {"weight", "backfire", "heaCost", "eneCost"}

    for stat, data in STAT_NAMES.items():
        if stat not in a and stat not in b:
            continue

        better = stat in lower_is_better

        right = left = ()

        if stat in a:
            value = a[stat]
            right = (1)

        else:
            left = ()


@commands.slash_command(guild_ids=TEST_GUILDS)
async def compare(inter: lib_types.ApplicationCommandInteraction, item1: str, item2: str) -> None:
    """Shows an interactive comparison of two items.

    Parameters
    -----------
    item1: First item to compare.
    item2: Second item to compare.
    """
    item_a = inter.bot.items_cache.get(item1)
    item_b = inter.bot.items_cache.get(item2)

    if item_a is None or item_b is None:
        raise commands.UserInputError("Either of specified items not found.")

    type_a = item_a.type
    type_b = item_b.type

    await inter.send(f"{item_a!r}\n\n{item_b!r}", ephemeral=True)


@item.autocomplete("name")
@compare.autocomplete("item1")
@compare.autocomplete("item2")
async def item_autocomplete(inter: lib_types.ApplicationCommandInteraction, input: str) -> list[str]:
    """Autocomplete for items"""
    if len(input) < 2:
        return ["Start typing to get suggestions..."]

    items = sorted(
        set(search_for(input, inter.bot.items_cache)) | inter.bot.item_abbrevs.get(input.lower(), set())
    )

    if len(items) <= 25:
        return items

    return items[:25]


def setup(bot: SMBot) -> None:
    bot.add_slash_command(item)
    bot.add_slash_command(compare)


def teardown(bot: SMBot) -> None:
    bot.remove_slash_command("item")
    bot.remove_slash_command("compare")