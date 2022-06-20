"""
Functions to reduce the amount of boilerplate code
replacing ui.Views
"""

import asyncio
import typing as t
from functools import partial

import disnake
from disnake.ui.item import Item

from lib_helpers import MessageInteraction

T = t.TypeVar("T")
BS = t.TypeVar("BS", disnake.ui.Button, disnake.ui.Select)
BS_CO = t.TypeVar("BS_CO", disnake.ui.Button, disnake.ui.Select, covariant=True)
I_CO = t.TypeVar("I_CO", bound=Item, covariant=True)
MI = t.TypeVar("MI", bound=disnake.MessageInteraction, covariant=True)
P = t.ParamSpec("P")


class Object(t.Protocol[BS_CO, P]):
    custom_id: property

    def __init__(*args: P.args, **kwargs: P.kwargs) -> None:
        ...

    async def callback(self, inter: disnake.MessageInteraction, /) -> None:
        ...


ItemCallbackType = t.Callable[[BS_CO, MI], t.Coroutine[t.Any, t.Any, None]]
CallbackType = t.Callable[[MI], t.Coroutine[t.Any, t.Any, None]]


class Listener:
    def __init__(
        self,
        client: disnake.Client,
        timeout: float = 180,
        check: t.Callable[[MI], bool] | None = None,
    ) -> None:
        self.client = client
        self.timeout = timeout
        self.run = True

        if check is None:

            def _check(*args: t.Any):
                return True

            check = _check

        self.check = check

        self.wait_task = asyncio.Event()
        self.timed_out = False
        self._callbacks: dict[str, CallbackType] = {}

    def add_item(self, item: Object[BS_CO, P]) -> t.Callable[[ItemCallbackType[BS_CO, MI]], BS_CO]:
        def wrapper(func: ItemCallbackType[BS_CO, MI]) -> BS_CO:
            item.callback = partial(func, item)  # type: ignore
            assert item.custom_id is not None
            self._callbacks[item.custom_id] = item.callback

            return item  # type: ignore

        return wrapper

    @t.overload
    def add_multiple_items(
        self, items: t.Sequence[BS_CO]
    ) -> t.Callable[[ItemCallbackType[BS_CO, MI]], t.Sequence[BS_CO]]:
        ...

    @t.overload
    def add_multiple_items(
        self, items: t.Sequence[t.Sequence[BS_CO]]
    ) -> t.Callable[[ItemCallbackType[BS_CO, MI]], t.Sequence[t.Sequence[BS_CO]]]:
        ...

    def add_multiple_items(self, items: t.Sequence[BS_CO] | t.Sequence[t.Sequence[BS_CO]]):
        def wrapper(func: ItemCallbackType[BS_CO, MI]):
            for item_or_row in items:
                if isinstance(item_or_row, t.Sequence):
                    for item in item_or_row:
                        item.callback = partial(func, item)
                        assert item.custom_id is not None
                        self._callbacks[item.custom_id] = item.callback

                else:
                    item_or_row.callback = partial(func, item_or_row)
                    assert item_or_row.custom_id is not None
                    self._callbacks[item_or_row.custom_id] = item_or_row.callback

            return items

        return wrapper

    async def dispatch(self, id: str, inter: MessageInteraction) -> None:
        if id in self._callbacks:
            await self._callbacks[id](inter)

    async def listen(self) -> None:
        while self.run:
            try:
                result: MessageInteraction = await self.client.wait_for(
                    "message_interaction", timeout=self.timeout, check=self.check
                )

            except asyncio.TimeoutError:
                self.timed_out = True
                self.wait_task.set()
                return

            await self.dispatch(result.data.custom_id, result)

    async def wait(self) -> bool:
        return await self.wait_task.wait() and self.timed_out
