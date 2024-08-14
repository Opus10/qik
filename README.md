
# Qik

Qik (*quick*) is a cached command runner primarily for Python monorepos. Like [make](https://www.gnu.org/software/make/), but with hash-based caching and advanced dependencies such as globs, imports, external packages, and more.

Qik's command caching ensures you never do redundant work. Parametrize commands across modules, watch and re-run them reactively, or filter commands since a git hash. Qik can dramatically improve CI and development time.

Although qik has special functionality with Python projects, any git-based repo can use qik as a command runner.

[Read the qik docs here](https://qik.build/en/stable/guide/) or [this blog post on why I built Qik](https://qik.build/en/stable/blog/2024/08/12/why-im-building-qik/).

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
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

Running `qik format` will parametrize `ruff format` in parallel over all available threads and configured modules. Use `-n` to adjust the number of threads and `-m` to supply modules:

```bash
qik format -n 2 -m b_module -m c_module
```

### Module Dependencies

Some commands, such as [pyright](https://github.com/microsoft/pyright) type checking, should re-run whenever module files, imported code, or third-party dependencies change:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

Running `qik check-types` will parametrize `pyright` over all modules. Modular commands will be cached unless the module's files or dependencies change.

We use the `qik.graph` plugin, which provides commands that are automatically used for building and analyzing the import graph.

### Command Dependencies

Command dependencies help order execution. For example, change `deps` of `command.check-types` to run type checking only after code has been successfully formatted:

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

Above we're using the [AWS S3](https://aws.amazon.com/pm/serv-s3/) cache. See [this section](https://qik.build/en/stable/caching/) for a deep dive on how caching works, along with how to configure remote caching.

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

See [the command runner section](https://qik.build/en/stable/commands#runner) for other advanced options, such as selecting commands based on cache status and setting the default [context profile](https://qik.build/en/stable/context).

## Next Steps

Read the following guide to become a qik expert:

- [Commands](https://qik.build/en/stable/commands): Configuring and running commands. Learn about all the dependencies, selectors, and runtime behavior.
- [Context](https://qik.build/en/stable/context): Using environment-based context and runtime profiles.
- [Caching](https://qik.build/en/stable/caching): How caching works and how to configure all cache types, including S3.
- [CI/CD](https://qik.build/en/stable/ci): Patterns for optimizing CI/CD time.

After this, read the:

- [Cookbook](https://qik.build/en/stable/cookbook) for command and CLI snippets.
- [Roadmap](https://qik.build/en/stable/roadmap) for all the exciting upcoming features.
- [Blog](https://qik.build/en/stable/blog) for updates, how-tos, and other articles.

## Disclaimer

Qik is currently in beta. Bumping the minor version (e.g. `0.1.0` to `0.2.0`) will indicate an API break until we release version `1.0.0`.

Be diligent when using qik in your CI/CD. We recommend including a [global dependency](https://qik.build/en/stable/commands#global) in your commands to regularly break the cache. We also recommend [understanding how the import graph is built](https://qik.build/en/stable/commands#module) when using module dependencies.
