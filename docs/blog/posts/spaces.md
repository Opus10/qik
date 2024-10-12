---
date:
  created: 2024-10-12
authors:
  - wes
---

# Introducing Spaces

As a monorepo grows, so does the number of dependencies, environments, and the complexity of keeping modules isolated from one another.

Qik [spaces](spaces.md) provide the foundation for isolation, both in command execution and code imports. Spaces enable virtual environments, dotenv files, and fencing of files in a monorepo. Plugins like [Pygraph](plugin_pygraph.md) use these constructs for import linting. Future plugins can use spaces for creating optimized docker containers and much more.

Let's dive in to the many use cases of spaces.

<!-- more -->

## Virtual Environments

Spaces can be used to execute commands in isolated virtual environments. Qik plugins such as the [UV plugin](plugin_uv.md) add integration with virtualenv providers like [UV](https://github.com/astral-sh/uv):

```bash
pip install "qik[uv]"
```

In `qik.toml`:

```toml
[plugins]
uv = "qik.uv"
```

Now let's provide a requirements file for our *default* space:

```toml
[spaces]
default = "requirements.txt"
```

With this, any command we run will be executed inside the virtual environment defined by `requirements.txt`. Commands will depend on two UV plugin commands: `uv.lock` for locking the virtualenv, and `uv.install` for installing it.

Let's create a full `qik.toml` example:

```toml
[plugins]
uv = "qik.uv"

[spaces]
default = "requirements.txt"

[commands]
lint = "ruff check ."
```

Invocations of `qik lint` will lock and install the virtualenv before running `ruff check .`. Subsequent invocations of locking the virtualenv will be cached locally until the `requirements.txt` file changes.

Lock files are stored in the repo cache by default, but lock files can also be manually specified:

```toml
[spaces.default]
venv = {reqs = "requirements.txt", lock = "requirements.lock"}
```

You can pin commands to any space. For example, tools like [ruff](https://github.com/astral-sh/ruff) don't need to be in the virtual environment of the main project:

```toml
[spaces]
default = "requirements.txt"
ruff = "requirements-ruff.txt"

[commands.pytest]
exec = "pytest ."
deps = ["**.py"]

[commands.ruff]
exec = "ruff check ."
space = "ruff"
```

When running all commands with `qik`, the `ruff` command will execute in the `ruff` space while `pytest` will execute in the `default` space.

See the [UV plugin](plugin_uv.md) docs for more ways to configure UV virtual environments in spaces.

## Dotenv Files

Spaces can also have dotenv files associated with them, ensuring commands operate in an isolated environment:

```toml
[spaces.default]
dotenv = ".env"
```

In this example, all commands in the default space will be executed within the environment defined by `.env`. This file will also be added to the dependencies of commands.

## Modular Parametrization

Spaces can own "modules" of a monorepo, which allows for command parametrization:

```toml
[spaces.default]
modules = ["my_module", "my/nested/module"]

[spaces.my-library]
modules = ["my_library_module"]
```

With this pattern, we can make generic commands not tied to a specific space, for example:

```toml
[commands]
test = "pytest {module.dir}"
```

Above, the `test` command will run across every module of every space in parallel. If spaces have different virtualenvs, those will be used during execution.

## Fences

Fences provide the ability to define boundaries of a particular space. For example, some internal modules may need to be isolated from other parts of a project:

```toml
[spaces.module-one]
fence = ["module_one"]

[spaces.module-two]
fence = ["module_two"]
```

Above, we've specified fences that encapsulate the files of two spaces. Plugins like [Pygraph](plugin_pygraph.md) can use this metadata for import linting. For example, installing Pygraph and running `qik pygraph.check` will ensure `module_two` and `module_one` are standalone modules in a monorepo.

If `module_two` needs to import `module_one`, it can be added to the fence:

```toml
[spaces.module-one]
fence = ["module_one"]

[spaces.module-two]
fence = ["module_two", "module_one"]
```

Fences are just glob patterns in the monorepo. It can be more convenient to add a space to a fence so that all globs of that space are included:

```toml
[spaces.module-one]
fence = ["module_one"]

[spaces.module-two]
fence = ["module_two", {type = "space", name = "module-one"}]
```

See the [Pygraph import linting docs](plugin_pygraph.md#import-linting) for more examples of how to set up fences for import linting, which inclues the ability to lint external dependencies too.

## Roots

By default, `qik` will run all commands across all spaces. Use `qik -s space-name` to only run commands in that space.

One can also define a `root` of a space to only select commands when inside that directory. For example:

```toml
[spaces.my-space]
root = "my/folder"
```

When a user is in `my/folder`, running `qik` will only select commands attached to `my-space`.

This setting is also useful for the `qikx` command described next.

## qikx

`qik` runs static commands that can be cached. For free-form commands with dynamic arguments, `qikx` can be used.

`qikx` is space aware. Let's define a space with a virtualenv:

```toml
[spaces.my-space]
root = "my/folder"
venv = "requirements.txt"
```

Now we can do `qikx executable@my-space arg1 arg2 --flag` to run `executable` in the virtualenv of `my-space` with arguments `arg1`, `arg2`, and the flag `--flag`.

Changing into the root of the space removes the need to do `@my-space` in the command invocation.

## Final Thoughts

[Spaces](spaces.md) add a powerful abstraction to `qik`, whether using the standard cached command runner or the dynamic `qikx` utility. This introducion of spaces also includes a new [plugin system](plugin.md) as well that features [virtual environments with UV](plugin_uv.md) and [import linting with Pygraph](plugin_pygraph.md). We intend to make more plugins for space-related use cases in the future, such as optimized dockerfile creation from spaces.

Enjoy!
