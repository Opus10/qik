<p align="center" style="padding-bottom: 1rem">
  <a href="https://qik.build"><img src="docs/static/logo.webp" alt="qik" width="40%"></a>
</p>

Qik (*quick*) is a cached command runner for modular monorepos. Like [make](https://www.gnu.org/software/make/), but with hash-based caching and advanced dependencies such as globs, imports, external packages, and much more.

Qik's command caching ensures you never do redundant work. Parametrize commands across modules, watch and re-run them reactively, or filter commands since a git hash. Qik can dramatically improve CI and local development time.

Although qik has special functionality with Python repos, any git-based project can use qik as a command runner.

[Read the docs here](https://qik.build).

## Installation

```bash
pip install qik
```

For local development, we recommend installing most optional dependencies with:

```bash
pip install "qik[dev]"
```

Qik is compatible with Python 3.10 - 3.12, Linux, OSX, and WSL.

## Quick Start

### File and Glob Dependencies

Here we use the `pip-compile` executable from [pip-tools](https://github.com/jazzband/pip-tools) to lock PyPI distributions. Create `qik.toml` with the following:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Running `qik lock` executes `pip-compile > requirements.txt`. Results are cached in your repo until `requirements.in` changes.

### Distribution Dependencies

Change `deps` to re-run this command if we upgrade `pip-tools`:

```toml
deps = ["requirements.in", {type = "dist", name = "pip-tools"}]
```

Installing a different version of `pip-tools` will break the command cache.

### Modular Commands

Parametrize commands over modules, for example, running the [ruff](https://docs.astral.sh/ruff/) code formatter:

```toml
modules = ["a_module", "b_module", "c_module"]

[commands.format]
exec = "ruff format {module.path}"
deps = ["{module.path}/**.py"]
cache = "repo"
```

Running `qik format` will parametrize `ruff format` in parallel over all available threads and configured modules. Use `-n` to adjust the number of threads and `-m` to supply modules:

```bash
qik format -n 2 -m b_module -m c_module
```

### Import Dependencies

Some commands, such as [pyright](https://github.com/microsoft/pyright) type checking, should re-run whenever imports change:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.check_types]
exec = "pyright {module.path}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

Running `qik check_types` will parametrize `pyright` over all modules. Modular commands will be cached unless the module's files or dependencies change.

We use the `qik.graph` plugin, which provides commands that are automatically used for building and analyzing the import graph.

### Command Dependencies

Command dependencies help order execution. For example, change `deps` of `command.check_types` to run type checking only after code has been successfully formatted:

```toml
deps = [
    {type = "module", name = "{module.name}"},
    {type = "command", name = "format"}
]
```

### Caching

We've shown examples of the `repo` cache, which stores metadata of the most recent runs in the repo. Qik offers both local and remote caches to store all command runs and their output.

To use these, first ensure commands have `artifacts` configured. For example, the `lock` command generates a `requirements.txt` file:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
cache = "local"
```

Above we're using the `local` cache. Versions of our `requirements.txt` will be stored in the `._qik/cache` folder. Qik supports [AWS S3](https://aws.amazon.com/pm/serv-s3/) as a [remote caching backend](caching.md).

### Command Line Interface

The core CLI functionality is as follows:

- `qik` to run all commands.
- `qik <cmd_name> <cmd_name>` to run specific commands.
- `--watch` to reactively run selected commands.
- `-f` to run without the cache.
- `-m` to run against specific modules.
- `-n` to set the number of threads.
- `--ls` to list commands instead of running them.

Some runtime behavior is configurable via the CLI:

- `--cache` to set the default cache.
- `--cache-when` to configure when to cache. Use `finished` to cache all results. By default only `success` runs are cached.
- `--isolated` to not run dependent commands.

These options are useful for selecting commands:

- `--since` to select commands based on changes since a git SHA.
- `--cache-type` to select commands by their cache type.
- `--cache-status` to select commands by their cache status (`warm` or `cold`).
- `--fail` to return a non-zero exit code if any commands are selected.

Finally, use `-p` to set the qik [context](context.md).

## Docs

[Read the qik docs here](https://qik.build) for more information on:

- Commands: A cookbook of common commands and creating module-specific commands.
- Dependencies: All dependencies, including global dependencies, constants, and file parts.
- Selectors: Selecting commands based on properties.
- Context: Using environment-based context and runtime profiles.
- Caching: How caching works and how to configure all cache types, including S3.
- Continuous Integration: Patterns for optimizing CI time.
- Plugins: How to create qik plugins, such as custom commands and cache backends.
