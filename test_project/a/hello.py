from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    import msgspec


def my_func():
    print("hi")


def hi() -> msgspec.Struct:
    requests.get()
