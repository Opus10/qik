
# qik

<style>
.md-content .md-typeset h1 { visibility: hidden; height: 0px; margin: 0px; padding: 0px; }
</style>

<p align="center" style="padding-bottom: 1rem">
  <a href="https://qik.build"><img src="static/logo.webp" alt="qik" width="40%"></a>
</p>

Qik (*quick*) is a cached command runner for modular monorepos. Like [make](https://www.gnu.org/software/make/), but with hash-based caching and advanced dependencies such as globs, imports, external packages, and much more.

Qik's command caching ensures you never do redundant work. Parametrize commands across modules, watch and re-run them reactively, or filter commands since a git hash. Qik can dramatically improve CI and local development time.

Although qik has special functionality with Python repos, any git-based project can use qik as a command runner.

## Installation

```bash
pip install qik
```

For local development, we recommend installing most optional dependencies with:

```bash
pip install "qik[dev]"
```

Qik is compatible with Python 3.10 - 3.12, Linux, OSX, and WSL. It requires [git](https://git-scm.com).

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

### Module Dependencies

Some commands, such as [pyright](https://github.com/microsoft/pyright) type checking, should re-run whenever module files or dependent imports change:

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

We've shown examples of the `repo` cache, which stores metadata of the most recent runs in the repo. Qik also offers local and remote caches. To use a remote cache, define command `artifacts`. For example, the `lock` command generates a `requirements.txt` file:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
cache = "s3"
```

Above we're using the [AWS S3](https://aws.amazon.com/pm/serv-s3/) cache. See [this section](caching.md) for a deep dive on how caching works, along with how to configure remote caching.

### Command Line Interface

The core CLI functionality is as follows:

- `qik` to run all commands.
- `qik <cmd_name> <cmd_name>` to run specific commands.
- `--watch` to reactively run selected commands.
- `--since` to select commands based on changes since a git reference.
- `-f` to run without the cache.
- `-m` to run against specific modules.
- `-n` to set the number of threads.
- `--ls` to list commands instead of running them.

See [the command runner section](commands.md#runner) for other advanced options, such as selecting commands based on cache status and setting the default [context profile](context.md).

## Next Steps

Read the following to become a qik expert:

- [Commands](commands.md): Configuring and running commands. Learn about all the dependencies, selectors, and runtime behavior.
- [Context](context.md): Using environment-based context and runtime profiles.
- [Caching](caching.md): How caching works and how to configure all cache types, including S3.
- [CI/CD](ci.md): Patterns for optimizing CI/CD time.
