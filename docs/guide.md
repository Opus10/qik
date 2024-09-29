
# Qik

Qik (*quick*) is an extensible command runner for monorepos. Like [make](https://www.gnu.org/software/make/), but with hash-based caching, advanced dependencies like globs and module imports, and execution in managed virtual environments.

Qik's command caching and module parametrization can dramatically improve local development and CI/CD time. Qik's plugin ecosystem offers remote S3 command caching, Python import graph linting, and much more.

Although qik is currently tailored towards Python repos, any project can use it.

## Installation

```bash
pip install qik
```

For local development, we recommend installing most optional dependencies with:

```bash
pip install "qik[dev]"
```

Qik is compatible with Python 3.10 - 3.12, Linux, OSX, and WSL. It requires [git](https://git-scm.com) for command caching.

## Quick Start

### Commands

Configure commands in `qik.toml`:

```toml
[commands]
format = "ruff format ."
lint = "ruff check . --fix"
type-check = "pyright"
```

Run `qik` to execute every command across available cores. `qik <cmd> ...` runs specific commands.

Specify `deps` to cache commands. Here we use `pip-compile` from [pip-tools](https://github.com/jazzband/pip-tools) to lock requirements:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
```

The requirements file from `qik lock` is cached locally until `requirements.in` changes.

Along with globs, commands can depend on constants, other commands, Python distributions, and more.

Here we update our previous command to depend on the `pip-tools` distribution, breaking the cache when the version changes:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = [
    "requirements.in",
    {type = "pydist", name = "pip-tools"}
]
```

Here we use command dependencies to ensure our linter runs after formatting:

```toml
[commands.format]
exec = "ruff format ."
deps = ["**.py"]

[commands.lint]
exec = "ruff check . --fix"
deps = ["**.py", {type = "command", name = "format"}]
```

The `qik.pygraph` plugin provides the `pygraph` dependency. Here we run [pyright](https://github.com/microsoft/pyright) over the `hello.world` module whenever its code or imported code changes:

```toml
[plugins]
pygraph = "qik.pygraph"

[commands.check-types]
exec = "pyright hello/world"
deps = [{type = "pygraph", pyimport = "hello.world"}]
```

### Caches

Cache results directly in your project with the `repo` cache:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Us the `qik.s3` plugin to create a shared remote cache using [AWS S3](https://aws.amazon.com/s3/):

```toml
[plugins]
s3 = "qik.s3"

[caches.remote]
type = "s3"
bucket = "qik-cache"

[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
cache = "remote"
```

We specify `artifacts` here to ensure `requirements.txt` is cached and restored.

### Spaces

Qik *spaces* define isolated environments and metadata for commands.

Here we create a space for our linting command. The `qik.uv` plugin uses [uv](https://github.com/astral-sh/uv) to build virtualenvs:

```toml
[plugins]
uv = "qik.uv"

[spaces]
ruff = "ruff-requirements.txt"

[commands.format]
exec = "ruff format ."
deps = ["**.py"]
space = "ruff"

[commands.lint]
exec = "ruff check . --fix"
deps = ["**.py", {type = "command", name = "format"}]
space = "ruff"
```

Running `qik` will lock and install the virtualenv for the `ruff` space and execute commands inside it. Changes to `ruff-requirements.txt` will break the cache of downstream commands.

Along with managing virtual environments, spaces can:

- Declare a `dotenv` file to automatically set environment variables.
- Declare a `root`. Running `qik` under this folder only selects commands in the space.

Here's a more complete example:

```toml
[spaces.my-app]
root = "app"
dotenv = "app.env"
venv = "requirements.txt"
```

### Modules

Spaces can define *modules* for command parametrization. Here we parametrize `pyright` over six modules across two spaces:

```toml
[spaces.first]
modules = ["a", "b", "c"]
venv = "requirements-first.txt"

[spaces.second]
modules = ["d", "e", "f"]
venv = "requirements-second.txt"

[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
```

Using `{module...}` in a command definition will automatically parametrize it over ever module in every space.

Use `qik check-types -s first` to specify spaces or `qik check-types -m b -m c` to specific modules.

### Fences

Plugins like `qik.pygraph` can leverage the `fence` of a space to perform import linting and other useful tasks:

```toml
[plugins]
pygraph = "qik.pygraph"

[spaces.first]
modules = ["a", "b", "c"]
fence = true
```

Running `qik pygraph.check` will ensure these modules only import each other. Add additional internal imports or a virtual environment to extend the fence:

```toml
[plugins]
pygraph = "qik.pygraph"

[spaces.first]
modules = ["a", "b", "c"]
fence = ["other/module"]
venv = "requirements.txt"
```

Include another space in the fence:

```toml
[spaces.first]
modules = ["a", "b", "c"]

[spaces.second]
modules = ["d", "e", "f"]
fence = [{type = "space", name = "first"}]
```

Running `qik pygraph.check -s second` will ensure the `second` space can import both it's modules and the `first` space's modules.

### Command Line Interface

The core CLI functionality is as follows:

- `qik` to run all commands.
- `qik <cmd_name> <cmd_name>` to select commands by name.
- `-m` to select by module.
- `-s` to select by space.
- `--watch` to reactively run selected commands.
- `--since` to select commands based on changes since a git reference.
- `-f` to run without the cache.
- `-n` to set the number of workers.
- `--ls` to list commands instead of running them.

See [the command runner section](commands.md#runner) for other advanced options, such as selecting commands based on cache status and setting the default [context profile](context.md).

## Next Steps

Read the following guide to become a qik expert:

- [Commands](commands.md): Configuring and running commands. Learn about all the dependencies, selectors, and runtime behavior.
- [Context](context.md): Using environment-based context and runtime profiles.
- [Caching](caching.md): How caching works and how to configure all cache types, including S3.
- [CI/CD](ci.md): Patterns for optimizing CI/CD time.

After this, read the:

- [Cookbook](cookbook.md) for command and CLI snippets.
- [Roadmap](roadmap.md) for all the exciting upcoming features.
- [Blog](blog/index.md) for updates, how-tos, and other articles.

## Disclaimer

Qik is currently in beta. Bumping the minor version (e.g. `0.1.0` to `0.2.0`) will indicate an API break until we release version `1.0.0`.

Be diligent when using qik in your CI/CD. We recommend including a [global dependency](commands.md#global) in your commands to regularly break the cache. We also recommend [understanding how the import graph is built](commands.md#pygraph) when using pygraph dependencies.
