from __future__ import annotations

import contextlib
import functools
from typing import TYPE_CHECKING, Any, Iterator, Literal, TypeAlias

import qik.lazy

if TYPE_CHECKING:
    import rich.console as rich_console

    Emoji: TypeAlias = Literal[
        "broken_heart",
        "construction",
        "eyes",
        "white_check_mark",
        "fast-forward_button",
        "heavy_minus_sign",
    ]
    Color: TypeAlias = Literal["cyan", "red", "green", "yellow"]
else:
    rich_console = qik.lazy.module("rich.console")


def fmt_msg(msg: str, emoji: Emoji | None = None, color: Color | None = None) -> str:
    if color:
        msg = f"[{color}]{msg}[/{color}]"

    if emoji:
        msg = f":{emoji}-emoji: {msg}"

    return msg


def print(msg: str, emoji: Emoji | None = None, color: Color | None = None, **kwargs: Any) -> None:
    get().print(fmt_msg(msg, emoji=emoji, color=color), **kwargs)


def print_exception() -> None:
    get().print_exception()


def rule(msg: str, emoji: Emoji | None = None, color: Color | None = None, **kwargs: Any) -> None:
    get().rule(fmt_msg(msg, emoji=emoji, color=color), align="left", style=color)


@contextlib.contextmanager
def capture() -> Iterator[None]:
    with get().capture():
        yield


@functools.cache
def get() -> rich_console.Console:
    return qik.lazy.object(rich_console.Console)  # type: ignore
