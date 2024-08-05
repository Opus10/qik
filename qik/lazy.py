import functools
import importlib
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class object(Generic[T]):
    def __init__(self, loader: Callable[[], T]) -> None:
        self._loader = loader

    @functools.cached_property
    def _object(self) -> T:
        return self._loader()

    def __enter__(self, *args, **kwargs) -> Any:
        return self._object.__enter__(*args, **kwargs)  # type: ignore

    def __exit__(self, *args, **kwargs) -> Any:
        return self._object.__exit__(*args, **kwargs)  # type: ignore

    def __getattr__(self, name: str) -> Any:
        if not name.startswith("__"):
            return getattr(self._object, name)
        else:
            return object.__getattribute__(self, name)


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
                    module_to_opt_install = {
                        "watchdog": "watch",
                        "grimp": "graph",
                        "rustworkx": "graph",
                        "boto3": "s3",
                    }
                    err_msg = f"{self._modname} could not be imported."

                    if opt_install := module_to_opt_install.get(self._modname):
                        err_msg += f' Do "pip install qik[{opt_install}]" or install the {self._modname} package to use qik.'
                    else:
                        err_msg += f" Install the {self._modname} package to use qik."
                    raise ModuleNotFoundError(err_msg) from exc
            else:
                raise

        return getattr(self._mod, attr)
