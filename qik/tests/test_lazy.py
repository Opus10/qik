import pytest
import rich.console as rich_console

import qik.lazy


def test_module(mocker):
    xxhash = qik.lazy.module("xxhash")
    assert xxhash.xxh128_hexdigest("hi") == "7d596ce5fcabaf622a2300bbd7ea6e9a"

    with pytest.raises(AttributeError):
        xxhash.bad_attr()

    with pytest.raises(ModuleNotFoundError, match="Install the bad package to use qik."):
        qik.lazy.module("bad").not_installed  # noqa

    mocker.patch.dict("qik.lazy._MODULE_TO_OPT_INSTALL", {"some_module": "opt_install"})
    with pytest.raises(ModuleNotFoundError, match=r'Do "pip install qik\[opt_install\]"'):
        qik.lazy.module("some_module").not_installed  # noqa


def test_object():
    console = qik.lazy.object(rich_console.Console)

    # Ensure we can access methods and enter/exit lazy objects
    console.print("hello")
    with console:
        pass
