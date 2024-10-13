# Plugins

Qik's plugin system allows for third-party commands, virtual env types, cache types, and dependency types.

We briefly overview how to make a plugin here and how some existing plugins integrate with qik. To read about existing qik plugins, see the [UV plugin](plugin_uv.md), [Pygraph plugin](plugin_pygraph.md) and [S3 plugin](plugin_s3.md).

## How it Works

Qik plugins can alter the following behavior of the qik command runner:

- New dependency types, such as the [Pygraph dependency type](plugin_pygraph.md).
- New virtual environment types, such as the [UV plugin](plugin_uv.md).
- New cache types, such as the [S3 plugin](plugin_s3.md).

Some plugins, such as [Pygraph](plugin_pygraph.md), also introduce new commands such as import linting.

Qik plugins can impact the `qik.toml` configuration file in a few ways:

- By introducing new `type` attribute choices for caches, virtualenvs, dependencies, etc.
- By introducing new config sections to the `plugins` section.

## Writing a Plugin

Qik plugins are written in Python and are configured in the `qikplugin.py` file of the plugin.

When writing a plugin, remember to keep unnecessary imports minimal and nested. For example, instead of:

```python
import requests

def my_func():
    requests.get()
```

Do:

```python
def my_func():
    import requests
    requests.get()
```

Another avenue is to use `qik.lazy` for lazy module imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import requests
else:
    import qik.lazy

    requests = qik.lazy.module("requests")

def my_func():
    requests.get()
```

The above ensures that `requests` is dynamically imported and also keeps type annotations accurate.

By using this strategy, you ensure that your plugin does not adversely impact the performance of running qik commands. Every plugin must be loaded on command invocation, and imports not needed to bootstrap configuration should be lazy or dynamic.

Next we're going to go over some examples of writing plugins.

## Writing a Cache Plugin

Here we overview how the [S3 plugin](plugin_s3.py) is written. This is the entire `qikplugin.py` file:

```python
import qik.conf


class S3Conf(qik.conf.Cache, frozen=True, tag="s3"):
    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None


qik.conf.register_type(S3Conf, "qik.s3.cache.factory")
```

To register a new cache type, call `qik.conf.register_type` with the configuration object for your cache. Define a configuration object by inheriting `qik.conf.Cache`, which is a [msgspec struct](). The `tag` field is the `type` a user can use when configuring a cache in `qik.toml`.

The configuration class has a factory function for constructing the cache object. Here's what this function looks like:

```python
import qik.ctx

def factory(name: str, conf: S3Conf) -> S3Cache:
    endpoint_url = qik.ctx.format(conf.endpoint_url)
    endpoint_url = None if endpoint_url == "None" else endpoint_url
    return S3Cache(
        bucket=qik.ctx.format(conf.bucket),
        prefix=qik.ctx.format(conf.prefix),
        aws_access_key_id=qik.ctx.format(conf.aws_access_key_id),
        aws_secret_access_key=qik.ctx.format(conf.aws_secret_access_key),
        aws_session_token=qik.ctx.format(conf.aws_session_token),
        region_name=qik.ctx.format(conf.region_name),
        endpoint_url=endpoint_url,
    )
```

The name of the cache and configuration object from `qik.toml` are fed in, and the factory returns an object that inherits `qik.cache.Local`. We use `qik.ctx.fmt` to ensure `{ctx.var}` strings in the cache configuration are properly formatted.

!!! remember
    Remote caches generally use the local cache as hot storage.

The remote S3 cache looks like this:

```python
class S3Cache(msgspec.Struct, qik.cache.Local, frozen=True, dict=True):
    """A custom cache using the S3 backend"""

    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None

    def remote_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return pathlib.Path(self.prefix) / f"{runnable.slug}-{hash}"

    @qik.func.cached_property
    def client(self) -> Client:
        return Client(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
        )

    def on_miss(self, *, runnable: Runnable, hash: str) -> None:
        super().pre_get(runnable=runnable, hash=hash)

        self.client.download_dir(
            bucket_name=self.bucket,
            prefix=self.remote_path(runnable=runnable, hash=hash),
            dir=self.base_path(runnable=runnable, hash=hash),
        )

    def post_set(self, *, runnable: Runnable, hash: str, manifest: qik.cache.Manifest) -> None:
        super().post_set(runnable=runnable, hash=hash, manifest=manifest)

        self.client.upload_dir(
            bucket_name=self.bucket,
            prefix=self.remote_path(runnable=runnable, hash=hash),
            dir=self.base_path(runnable=runnable, hash=hash),
        )
```

In other words, we override `on_miss` to download from S3 if we miss the local cache. We override `post_set` to upload to S3 once the cache value has been set locally.

## Writing a Virtualenv Plugin

Virtualenv plugins follow a similar pattern as caches. A config object and factory are registered, providing a new virtualenv `type` for use in `qik.toml`. Here's an example of `qikplugin.py` for [UV](plugin_uv.md):

```python
import qik.conf
import qik.unset

class UVVenvConf(qik.conf.Venv, frozen=True, tag="uv"):
    python: str | qik.unset.UnsetType = qik.unset.UNSET
    constraint: str | qik.conf.SpaceLocator | qik.unset.UnsetType = qik.unset.UNSET
    install_cmd: ClassVar[str] = "uv.install"


qik.conf.register_type(UVVenvConf, "qik.uv.venv.factory")
```

In this case, `uv` is the new `type` provided in the virtualenv config of a space. A factory then creates a virtualenv that inherits `qik.venv.Venv`:

```python
class UVVenv(qik.venv.Venv, frozen=True, dict=True):
    conf: UVVenvConf

    @qik.func.cached_property
    def python(self) -> str | None:
        return qik.unset.coalesce(
            self.conf.python, qik.uv.conf.get().python, default=None
        )

    @qik.func.cached_property
    def constraint(self) -> str | None:
        try:
            return qik.unset.coalesce(
                _resolve_constraint(self.conf.constraint),
                _resolve_constraint(qik.uv.conf.get().constraint),
                default=None,
            )
        except RecursionError as e:
            raise qik.errors.CircularConstraint("Circular constraint detected.") from e

    @qik.func.cached_property
    def default_lock(self) -> str:
        uv_conf = qik.uv.conf.get()
        root = (
            qik.conf.pub_work_dir(rel=True)
            if uv_conf.resolved_cache == "repo"
            else qik.conf.priv_work_dir(rel=True)
        )
        return str(
            root
            / "artifacts"
            / qik.uv.utils.lock_cmd_name()
            / f"requirements-{self.name}-lock.txt"
        )

    @qik.func.cached_property
    def lock(self) -> str:
        super_lock = super().lock
        return self.default_lock if not super_lock else super_lock

    @qik.func.cached_property
    def environ(self) -> dict[str, str]:  # type: ignore
        return os.environ | {
            "VIRTUAL_ENV": str(self.dir),
            "PATH": f"{self.dir}/bin:{os.environ['PATH']}",
        }

    @qik.func.cached_property
    def dir(self) -> pathlib.Path:  # type: ignore
        return qik.conf.priv_work_dir() / "venv" / self.name

    @qik.func.cached_property
    def site_packages_dir(self) -> pathlib.Path:  # type: ignore
        for path in pathlib.Path(self.dir).glob("lib/python*/site-packages"):
            return path

        # TODO: Turn this into a qik runtime error
        raise AssertionError(
            f'Could not find site packages dir of venv "{self.name}" at "{self.dir}"'
        )

    @qik.func.cached_property
    def runnable_deps(self) -> dict[str, qik.dep.Runnable]:
        return {
            runnable.name: qik.dep.Runnable(name=runnable.name, obj=runnable, strict=True)
            for runnable in qik.cmd.load(
                qik.uv.utils.install_cmd_name(), space=self.name
            ).runnables.values()
        }


def factory(name: str, conf: UVVenvConf) -> UVVenv:
    return UVVenv(name=name, conf=conf)
```

The most important pieces of a `Venv` object are:

- `runnable_deps`: Any runnable dependencies that are injected into commands of the virtualenv. For example, UV injects locking and installation runnable dependencies that run before the command.
- `site_packages_dir`: The Python site packages dir so that `pydist` dependencies are properly discovered.
- `dir`: Where the virtualenv actually resides.
- `environ`: The environment variables to use in the running command process.

## Writing a Dependency Plugin

The [Pygraph plugin](plugin_pygraph.md) introduces a new `pygraph` dependency type. The type is registered similar to other plugin types in `qikplugin.py`:

```python
import qik.conf

class PygraphDepConf(qik.conf.Dep, tag="pygraph", frozen=True):
    pyimport: str


qik.conf.register_type(PygraphDepConf, "qik.pygraph.dep.factory")
```

In this case, `pygraph` is a new `type` allowed when specifying `deps` of a command in `qik.toml`. The dependency factory looks like this:

```python
import qik.dep

class PygraphDep(qik.dep.BaseCmd, frozen=True):
    """A python module and its associated imports."""

    strict: ClassVar[bool] = True
    space: str | None = None

    def get_cmd_name(self) -> str:
        return qik.pygraph.utils.lock_cmd_name()

    def get_cmd_args(self) -> dict[str, str | None]:
        return {"pyimport": self.val, "space": self.space}

    @property
    def globs(self) -> list[str]:  # type: ignore
        return [str(qik.pygraph.utils.lock_path(self.val, self.space))]


def factory(
    conf: PygraphDepConf,
    module: qik.conf.ModuleLocator | None = None,
    space: str | None = None,
) -> PygraphDep:
    return PygraphDep(qik.ctx.format(conf.pyimport, module=module), space=space)
```

In other words, the `pygraph` dependency type is actually a dependency to the `pygraph.lock` command and the output file of this command.

## Writing Plugin Commands

Plugins can include `qik.toml` files that include new commands. Some commands, such as those included by `pygraph`, are usually "hidden" and only included in the command graph when depended on by another command.

!!! remember

    If writing a plugin that just includes commands in a `qik.toml`, you'll still need an empty `qikplugin.py` file.

## Including Custom Plugin Configuration

Some plugins require custom configuration. To support plugin configuration in `qik.toml`, register a new config object for your plugin:

```python
import qik.conf

class PygraphPluginConf(qik.conf.PluginConf, frozen=True, dict=True, tag="qik.pygraph"):
    ignore_type_checking: bool = False
    ignore_pydists: bool = False
    cache: str | qik.unset.UnsetType = qik.unset.UNSET
    build_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    lock_cache: str | qik.unset.UnsetType = qik.unset.UNSET
    check_cache: str | qik.unset.UnsetType = qik.unset.UNSET

qik.conf.register_conf(PygraphPluginConf)
```

Unlike other object types, configuration objects don't need a factory. When a configuration type is registered, users can include configuration under `[pluigns.plugin-name]` in `qik.toml`.

Plugin authors should use `qik.conf.plugin("dotted.plugin.path")` to object the structured configuration for a plugin.
