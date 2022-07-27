from __future__ import annotations

import typing as t

from typing_extensions import NotRequired

AnyType = t.Literal[
    "TORSO",
    "LEGS",
    "DRONE",
    "SIDE_WEAPON",
    "TOP_WEAPON",
    "TELEPORTER",
    "CHARGE_ENGINE",
    "GRAPPLING_HOOK",
    "MODULE",
]
AnyElement = t.Literal["PHYSICAL", "EXPLOSIVE", "ELECTRIC", "COMBINED"]

# fmt: off
AnyMechStatKey = t.Literal[
    "weight",    "health", "eneCap", "eneReg", "heaCap", "heaCol", "bulletCap",
    "rocketCap", "phyRes", "expRes", "eleRes", "walk",   "jump"
]

AnyStatKey = AnyMechStatKey | t.Literal[
    "phyDmg", "phyResDmg", "expDmg", "heaDmg", "heaCapDmg", "heaColDmg",
    "expResDmg", "eleDmg", "eneDmg", "eneCapDmg", "eneRegDmg", "eleResDmg",
    "range", "push", "pull", "recoil", "retreat", "advance", "walk",
    "jump", "uses", "backfire",  "heaCost", "eneCost", "bulletCost", "rocketCost"
]
# fmt: on


class StatName(t.TypedDict):
    default: str
    in_game: NotRequired[str]
    short: NotRequired[str]


class StatBuff(t.TypedDict):
    mode: t.Literal["+", "+%", "-%", "+2%"]
    range: t.Literal[11, 12]


class StatDict(t.TypedDict):
    names: StatName
    emoji: NotRequired[str]
    beneficial: NotRequired[t.Literal[False]]
    buff: NotRequired[StatBuff]


class AnyStats(t.TypedDict, total=False):
    # stats sorted in order they appear in-game
    weight: int
    health: int
    eneCap: int
    eneReg: int
    heaCap: int
    heaCol: int
    bulletCap: int
    rocketCap: int
    phyRes: int
    expRes: int
    eleRes: int
    phyDmg: list[int]
    phyResDmg: int
    eleDmg: list[int]
    eneDmg: int
    eneCapDmg: int
    eneRegDmg: int
    eleResDmg: int
    expDmg: list[int]
    heaDmg: int
    heaCapDmg: int
    heaColDmg: int
    expResDmg: int
    walk: int
    jump: int
    range: list[int]
    push: int
    pull: int
    recoil: int
    advance: int
    retreat: int
    uses: int
    backfire: int
    heaCost: int
    eneCost: int
    bulletCost: int
    rocketCost: int


class AnyMechStats(t.TypedDict, total=False):
    weight: int
    health: int
    eneCap: int
    eneReg: int
    heaCap: int
    heaCol: int
    bulletCap: int
    rocketCap: int
    phyRes: int
    expRes: int
    eleRes: int
    # walk & jump appear after expResDmg
    walk: int
    jump: int


class Attachment(t.TypedDict):
    x: int
    y: int


Attachments = dict[str, Attachment]
AnyAttachment = Attachment | Attachments | None
AttachmentType = t.TypeVar("AttachmentType", bound=AnyAttachment)


class ItemDictBasev2(t.TypedDict):
    name: str
    type: AnyType
    element: AnyElement
    transform_range: str
    common: NotRequired[AnyStats]
    max_common: NotRequired[AnyStats]
    rare: NotRequired[AnyStats]
    max_rare: NotRequired[AnyStats]
    epic: NotRequired[AnyStats]
    max_epic: NotRequired[AnyStats]
    legendary: NotRequired[AnyStats]
    max_legendary: NotRequired[AnyStats]
    mythical: NotRequired[AnyStats]
    max_mythical: NotRequired[AnyStats]
    divine: NotRequired[AnyStats]
    width: NotRequired[int]
    height: NotRequired[int]


class ItemDictAttachmentv2(ItemDictBasev2):
    attachment: Attachment


class ItemDictAttachmentsv2(ItemDictBasev2):
    attachment: Attachments


ItemDictv2 = ItemDictBasev2 | ItemDictAttachmentv2 | ItemDictAttachmentsv2


class ItemDictBase(t.TypedDict):
    id: int
    name: str
    image: NotRequired[str]
    width: NotRequired[int]
    height: NotRequired[int]
    type: AnyType
    element: AnyElement
    transform_range: str
    stats: AnyStats
    tags: NotRequired[list[t.Literal["sword", "melee", "roller"]]]


class ItemDictAttachment(ItemDictBase):
    attachment: Attachment


class ItemDictAttachments(ItemDictBase):
    attachment: Attachments


ItemDict = ItemDictBase | ItemDictAttachment | ItemDictAttachments


class PackConfig(t.TypedDict):
    key: str
    name: str
    base_url: str
    description: str


class ItemPack(t.TypedDict):
    config: PackConfig
    items: list[ItemDict]


class SpritePosition(t.TypedDict):
    width: int
    height: int
    x: int
    y: int


class ItemPackv2(t.TypedDict):
    version: str
    key: str
    name: str
    description: str
    spritesSheet: str
    spritesMap: dict[str, SpritePosition]
    items: list[ItemDict]


class TagsDict(t.TypedDict):
    premium: bool
    sword: bool
    melee: bool
    roller: bool
    legacy: bool
    require_jump: bool
    custom: bool


class ItemSerialized(t.TypedDict):
    slotName: str
    id: int
    name: str
    type: str
    stats: AnyStats
    tags: TagsDict
    element: str
    timesUsed: t.Literal[0]


class MechSerialized(t.TypedDict):
    name: str
    setup: list[int]


class WUSerialized(t.TypedDict):
    name: str
    itemsHash: str
    mech: MechSerialized
