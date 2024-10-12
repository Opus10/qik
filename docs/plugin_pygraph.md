# The Pygraph Plugin

Qik's pygraph plugin provides dependency types and commands that utilize the Python import graph. Here we overview the primary two use cases: [Import Graph Dependencies](#import-graph-dependencies) and [Import Linting](#import-linting).

## Installation

The pygraph plugin requires additional dependencies. `pip install "qik[dev]"` to get all dev dependencies including pygraph. Otherwise, `pip install "qik[pygraph]"`.

!!! note

    One can manually install `grimp` and `rustworkx` too.

After this, configure the plugin in `qik.toml`:

```toml
[plugins]
pygraph = "qik.pygraph"
```

<a id="import-graph-dependencies"></a>

## Import Graph Dependencies

Pygraph provides the `pygraph` dependency type, allowing for commands to depend on a Python module's files and import graph. This includes both internal files and external distributions.

### Usage

Below we only run type checking over a module when the import graph changes:

```toml
[plugins]
pygraph = "qik.pygraph"

[type-check]
exec = "pyright my/module"
deps = [{type = "pygraph", pyimport = "my.module"}]
```

When using the `pygraph` dependency type, the following dependencies are automatically added:

- Python files internal to the module referenced by `pyimport`.
- Python imported by the module referenced by `pyimport`.
- External `pydist` dependencies referenced by any of the above files.

In other words, changes to any Python distributions or files associated with `pyimport` will break the cache.

!!! remember

    If your `pyimport` is `my.module`, this means `my.module.submodule`'s files and imports are also included.

One can use [parametrized commands](commands.md#parametrized-commands) and leverage the `pyimport` property of modules like so:

```toml
[spaces.default]
modules = ["my_module_a", "nested_module/b", "module_c"]

[command.type-check]
exec = "pyright {module.dir}"
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
```

Above we are running `pyright` over the directory of each module. We use the python import path of the modules as an argument to the `pygraph` dependency type.

### How it Works

When using the `pygraph` dependency type, qik adds dependent commands to build and lock the import graph. The generated lock files contain all dependent glob patterns and distributions of the module, including imports in `TYPE_CHECKING` blocks.

To ignore `TYPE_CHECKING` imports or ignore distributison from the import graph, override the pygraph plugin configuration:

```toml
[plugins.pygraph]
pyimport = "qik.pygraph"
ignore-type-checking = true
ignore-pydists = true
```

Qik only discovers `import` statements, even if they are nested in function. Qik does not discover dynamic imports such as django's [apps.get_model](https://docs.djangoproject.com/en/5.0/ref/applications/#django.apps.AppConfig.get_models). To ensure accuracy in your import graph, do either of:

- Add a standalone file in your module (such as `qikimports.py`) with the non-dynamic imports.
- Do dynamic imports outside of `TYPE_CHECKING`. For example:

        from typing import TYPE_CHECKING

        from django.apps import apps

        if TYPE_CHECKING:
            # Qik will discover this import
            from my_app.models import MyModel
        else:
            # Do dynamic or lazy importing in the app
            MyModel = apps.get_model("my_app", "MyModel")

!!! warning

    Dynamic imports that use variables to determine the import path are not supported.

### Troubleshooting External Distributions

Optional distributions that aren't installed in the virtual environment may lead to mapping and version resolution errors. Instead of globally turning off distributions, see the troubleshooting section on [mapping modules to distributions](errors.md#graph0) and [overriding distribution versions](errors.md#dep0) for ways around this.

Remember, only direct third-party imports are included in the graph. If, for example, you import the `x-dist` PyPI package and `x-dist` imports `y-dist`, the cache will not be invalidated when upgrading `y-dist` unless it is directly imported in your code.

<a id="import-linting"></a>

## Import Linting

The `pygraph.check` command provides import linting for [fence-enabled spaces](spaces.md#fences).

Assume the following folder structure:

```
foo/
bar/
baz/
  - sub_module/
other/
  - a/
  - b/
```

Imagine we have these three spaces configured:

```toml
[plugins]
pygraph = "qik.pygraph"

[spaces.baz]
fence = ["baz"]

[spaces.foo]
venv = "requirements.txt"
fence = ["foo", "other/a"]

[spaces.bar]
fence = ["bar", {type = "space", name = "foo"}]
```

Running `qik pygraph.check` will check the import graph for all three spaces:

- **baz**: The fence of `baz` ensures Python files under `baz/` can only import internal files from this folder. Since there is no virtualenv configured, only external imports from the active virtualenv are allowed.
- **foo**: The fence around `foo` allows Python files under `foo/` and `other/a/` to import one another. Since `foo` has a virtualenv configured, only external imports from the locked `requirements.txt` are allowed.
- **bar**: The `bar` fence ensures Python files under `bar/` can import one another along with importing the files in the `foo` fence. Since `bar` has no virtualenv configured, only external imports from the active virtualenv are allowed.

Remember the following when using the import linting command:

- Spaces without a fence are not checked.
- Use `-s` to specify a space or multiple spaces, e.g. `qik pygraph.check -s foo -s bar`.
- You must configure a virtualenv plugin to use import linting for a non-active virtualenv. The [UV plugin](plugin_uv.md) is recommended for this.
- When adding a space to a fence, the virtualenv of that space is not included in the fence. Be sure that the virtualenv of the parent space includes the necessary dependencies for all child spaces.
- The `pygraph.build` command is a dependency of `pygraph.check`. Import linting runs from the local cache by default. To speed up CI/CD or remote environments, consider configuring a non-local cache. More on this in the next section.

## Caching

By default, all commands use `[defaults.cache]` as the default cache. This defaults to the `local` cache.

To avoid re-building the import graph across your project in CI, one can use the `repo` cache or a [custom remote cache](caching.md#remote) for the pygraph commands like below:

```toml
[plugins.pygraph]
pyimport = "qik.pygraph"
build-cache = "repo"
lock-cache = "repo"
check-cache = "repo"
```

To set the default cache for all pygraph commands, do:

```toml
[plugins.pygraph]
pyimport = "qik.pygraph"
cache = "repo"
```
