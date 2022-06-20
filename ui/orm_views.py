from __future__ import annotations

import inspect
import operator as op
import typing as t

from typing_extensions import Self

T = t.TypeVar("T")
T_CO = t.TypeVar("T_CO", covariant=True)
RetT = t.TypeVar("RetT")


class Selector(t.Generic[T, RetT]):
    parent_cls: t.Type[T]
    wrapped: t.Callable[[T], RetT]
    ret_type: RetT

    def __init__(self, func: t.Callable[[T], RetT], attribute: str | None = None) -> None:
        self.wrapped = func
        self.attribute = attribute or func.__name__
        self.ret_type = inspect.signature(func).return_annotation

        if type(self.ret_type) is str:
            self.ret_type = t.get_type_hints(func).get("return", None)

            if self.ret_type is None:
                raise TypeError("Function return type unspecified")

    def __repr__(self) -> str:
        if not hasattr(self, "parent_cls"):
            return f"<Accessor(...)>"
        return f"<Accessor({self.parent_cls.__name__}.{self.wrapped.__name__})>"

    @t.overload  # No parent instance -> accessed on the class
    def __get__(self, parent: None, parent_cls: type[T]) -> Self:
        ...

    @t.overload  # accessed on the instance
    def __get__(self, parent: T, parent_cls: type[T]) -> RetT:
        ...

    def __get__(self, parent: T | None, parent_cls: type[T]) -> Self | RetT:
        if parent is None and parent_cls is None:
            raise TypeError("OperatorDescriptor must be used as a descriptor on a class.")

        self.parent_cls = parent_cls

        # accessed on an instance -> return the instance value
        if parent is not None:
            return self.wrapped(parent)

        # accessed on the class -> return the OperatorDescriptor
        return self

    @property
    def type(self) -> RetT:
        return AttributeProxy(self.ret_type, self.attribute)  # type: ignore

    def __eq__(self, other: t.Any) -> Operator[T]:
        return Operator(op.eq, self, other)

    def __gt__(self, other: RetT) -> Operator[T]:
        return Operator(op.gt, self, other)

    def __ge__(self, other: RetT) -> Operator[T]:
        return Operator(op.ge, self, other)

    def __lt__(self, other: RetT) -> Operator[T]:
        return Operator(op.lt, self, other)

    def __le__(self, other: RetT) -> Operator[T]:
        return Operator(op.le, self, other)


class Item:
    pass


IT_CO = t.TypeVar("IT_CO", bound=Item, covariant=True)


class Operator(t.Generic[T_CO]):
    def __init__(self, func: t.Callable[[t.Any, t.Any], bool], right: t.Any, left: t.Any) -> None:
        self.func = func
        self.right = right
        self.left = left

    def __repr__(self) -> str:
        return f"<Operator {self.func} {self.right} {self.left}>"

    def __or__(self, other: Operator[T_CO] | bool) -> Operator[T_CO]:
        return Operator(op.or_, self, other)

    __ror__ = __or__

    def __and__(self, other: Operator[T_CO] | bool) -> Operator[T_CO]:
        return Operator(op.and_, self, other)

    __rand__ = __and__

    def __eq__(self, other: t.Any) -> Operator[T_CO]:
        return Operator(op.eq, self, other)

    def __gt__(self, other: t.Any) -> Operator[T_CO]:
        return Operator(op.gt, self, other)

    def __ge__(self, other: t.Any) -> Operator[T_CO]:
        return Operator(op.ge, self, other)

    def __lt__(self, other: t.Any) -> Operator[T_CO]:
        return Operator(op.lt, self, other)

    def __le__(self, other: t.Any) -> Operator[T_CO]:
        return Operator(op.le, self, other)

    def get(self, value: Item) -> bool:
        if isinstance(self.right, Operator):
            r_val = self.right.get(value)

        elif isinstance(self.right, Selector):
            r_val = getattr(value, self.right.attribute)

        elif isinstance(self.right, AttributeProxy):
            r_val = self.right.get(value)

        else:
            r_val = self.right

        if isinstance(self.left, Operator):
            l_val = self.left.get(value)

        elif isinstance(self.left, Selector):
            l_val = getattr(value, self.left.attribute)

        elif isinstance(self.left, AttributeProxy):
            l_val = self.left.get(value)

        else:
            l_val = self.left

        return self.func(r_val, l_val)


class AttributeProxy(t.Generic[RetT]):
    def __init__(self, type: RetT, attribute: str) -> None:
        self.type = type
        self.attribute = attribute
        self.method: t.Callable[..., bool] | None = None
        self.args: tuple[t.Any, ...] | None = None
        self.kwargs: dict[str, t.Any] | None = None

    def __repr__(self) -> str:
        return f"<AttributeProxy {self.type!r} {self.method!r} {self.args} {self.kwargs}>"

    def __getattr__(self, name: str) -> Self:
        if self.method is not None:
            raise AttributeError("Attempted to fetch an attribute twice.")

        val = getattr(self.type, name)

        if not callable(val):
            raise TypeError("The fetched attribute has to be a method.")

        self.method = val
        return self

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> Self:
        if self.method is None:
            raise TypeError("This object is not callable in this context")

        if not (self.args is self.kwargs is None):
            raise TypeError("Method called twice.")

        self.args = args
        self.kwargs = kwargs

        return self

    def get(self, value: t.Any) -> bool:
        if self.method is None or self.args is None or self.kwargs is None:
            raise TypeError("get called before callable was obtained")

        return self.method(getattr(value, self.attribute), *self.args, **self.kwargs)


class Manager(t.Generic[IT_CO]):
    def __init__(self, *items: IT_CO) -> None:
        self.items = items

    def find(self, pred: Operator[IT_CO] | bool, /) -> IT_CO | None:
        assert not isinstance(pred, bool)

        for item in self.items:
            if pred.get(item):
                return item

        return None

    def find_all(self, pred: Operator[IT_CO] | bool, /) -> list[IT_CO]:
        assert not isinstance(pred, bool)
        return [item for item in self.items if pred.get(item)]


class Button(Item):
    def __init__(self, custom_id: str, f: int = 0) -> None:
        self._custom_id = custom_id
        self.f = f

    def __repr__(self) -> str:
        return f"<Button {self.custom_id!r}>"

    @Selector
    def custom_id(self) -> str:
        return self._custom_id

    @Selector
    def foo(self) -> int:
        return self.f


if __name__ == "__main__":
    manager = Manager(Button("yeah"), Button("nah", 1), Button("foh", 2))
    print(manager.find(Button.custom_id == "yeah"))
    print(manager.find_all(Button.foo <= 1))
    print(manager.find_all((Button.foo <= 1) & (Button.custom_id == "yeah")))
    print(manager.find_all(0 <= Button.foo <= 1))
    print(manager.find_all(Button.custom_id.type.startswith("n")))
    print(manager.find_all(Button.custom_id.type.startswith("n") | (Button.foo <= 1)))
