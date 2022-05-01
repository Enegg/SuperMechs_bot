from __future__ import annotations

import typing as t
from io import BytesIO

import aiohttp
import disnake
from PIL import Image

if t.TYPE_CHECKING:
    from .item import Item
    from .types import Attachment, Attachments


async def get_image(link: str, session: aiohttp.ClientSession) -> Image.Image:
    async with session.get(link) as response:
        response.raise_for_status()
        return Image.open(BytesIO(await response.content.read()))


def image_to_file(image: Image.Image, filename: str | None = None) -> disnake.File:
    """Creates a `disnake.File` object from `PIL.Image.Image`."""
    # not using with as the stream is closed by the File object
    stream = BytesIO()
    image.save(stream, format="png")
    stream.seek(0)
    return disnake.File(stream, filename)


class MechRenderer:
    layer_order = (
        "drone",
        "side2",
        "side4",
        "top2",
        "leg2",
        "torso",
        "leg1",
        "top1",
        "side1",
        "side3",
    )

    def __init__(self, torso: Item[Attachments]) -> None:
        self.torso_image = torso.image
        # how many pixels the complete image extends beyond torso image canvas
        self.pixels_left = 0
        self.pixels_right = 0
        self.pixels_above = 0
        self.pixels_below = 0
        self.torso_attachments = torso.attachment

        self.images: list[tuple[int, int, Image.Image] | None] = [None] * 10

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"offsets={(self.pixels_left, self.pixels_right, self.pixels_above, self.pixels_below)}"
            f" images={self.images} at 0x{id(self):016X}>"
        )

    def add_image(self, item: Item[Attachment], layer: str) -> None:
        if layer == "legs":
            self.add_image(item, "leg1")
            self.add_image(item, "leg2")
            return

        item_x = item.attachment["x"]
        item_y = item.attachment["y"]

        if layer == "drone":
            x, y = -item_x, -item_y

        else:
            offset = self.torso_attachments[layer]
            x = offset["x"] - item_x
            y = offset["y"] - item_y

        self.adjust_offsets(item.image, x, y)
        self.put_image(item.image, layer, x, y)

    def adjust_offsets(self, image: Image.Image, x: int, y: int) -> None:
        self.pixels_left = max(self.pixels_left, -x)
        self.pixels_above = max(self.pixels_above, -y)
        self.pixels_right = max(self.pixels_right, x + image.width - self.torso_image.width)
        self.pixels_below = max(self.pixels_below, y + image.height - self.torso_image.height)

    def put_image(self, image: Image.Image, layer: str, x: int, y: int) -> None:
        self.images[self.layer_order.index(layer)] = (x, y, image)

    def finalize(self) -> Image.Image:
        self.put_image(self.torso_image, "torso", 0, 0)

        canvas = Image.new(
            "RGBA",
            (
                self.torso_image.width + self.pixels_left + self.pixels_right,
                self.torso_image.height + self.pixels_above + self.pixels_below,
            ),
            (0, 0, 0, 0),
        )

        for x, y, image in filter(None, self.images):
            canvas.alpha_composite(image, (x + self.pixels_left, y + self.pixels_above))

        return canvas
