import importlib
from typing import Any, Callable, Final, Generic, TypeVar

import qik.func

T = TypeVar("T")
_MODULE_TO_OPT_INSTALL: Final = {
    "watchdog": "watch",
    "grimp": "pygraph",
    "rustworkx": "pygraph",
    "boto3": "s3",
}


class object(Generic[T]):
    def __init__(self, loader: Callable[[], T]) -> None:
        self._loader = loader

    @qik.func.cached_property
    def _object(self) -> T:
        return self._loader()

    def __enter__(self, *args, **kwargs) -> Any:
        return self._object.__enter__(*args, **kwargs)  # type: ignore

    def __exit__(self, *args, **kwargs) -> Any:
        return self._object.__exit__(*args, **kwargs)  # type: ignore

    def __getattr__(self, name: str) -> Any:
        return getattr(self._object, name)


class module:
    def __init__(self, modname: str) -> None:
        self._modname = modname
        self._mod = None

    def __getattr__(self, attr: str) -> Any:
        try:
            return getattr(self._mod, attr)
        except Exception:
            if self._mod is None:
                try:
                    self._mod = importlib.import_module(self._modname)
                except ModuleNotFoundError as exc:
                    err_msg = f"{self._modname} could not be imported."
                    package = self._modname.split(".", 1)[0]

                    if opt_install := _MODULE_TO_OPT_INSTALL.get(package):
                        err_msg += f' Do "pip install qik[{opt_install}]" or install the {package} package to use qik.'
                    else:
                        err_msg += f" Install the {package} package to use qik."
                    raise ModuleNotFoundError(err_msg) from exc
            else:
                raise

        return getattr(self._mod, attr)
