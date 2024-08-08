from typing import TYPE_CHECKING

import grimp
import requests

if TYPE_CHECKING:
    import textualize


def my_func():
    print("hi")


def hi() -> textualize.textualize:
    requests.get()
    hi = grimp.main()
    assert hi
