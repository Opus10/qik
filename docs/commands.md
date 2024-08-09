# Commands

Commands are the core construct of qik. Here we overview configuration, explain how to create module-specific commands, dive into command dependencies, and end with a section on the command runner.

!!! warning

    Qik is still in alpha and these docs are incomplete.

## Basic Configuration

Let's first dive into the anatomy of a command, using an example `qik.toml`:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
```

In its simplest form, a command is just a shell string, executed with the same working directory as your root `qik.toml`. This command has no dependencies specified, so it's unable to be cached. It's named `lock`, so it can be executed with `qik lock`.

To leverage command caching, specify the following two properties:

1. `deps` - A list of [dependencies](dependencies.md).
2. `cache` - The [cache](caching.md) to use.

To leverage a remote cache, also specify the `artifacts` created or edited by the command.

In the above example, we're compiling a lock file. We're caching results directly in our repo, so we can update the command to:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

!!! note

    If using a remote cache such as [s3](caching.md), we'd configure this cache in our `qik.toml` and set `artifacts = ["requirements.txt"]` since this command is generating a requirements file.

## Parametrizing Modular Commands

To run commands across modules, first configure them like so:

```toml
modules = ["my_module_a", "nested_module.b", "module_c"]
```

Parametrize your command across modules by using the `{module}` variable in your configuration. Here we format our modules:

```toml
modules = ["my_module_a", "nested_module.b", "module_c"]

[command.lint]
exec = "ruff format {module.path}"
deps = ["{module.path}/**.py"]
cache = "repo"
```

When using the `{module}` variable, one has access to `module.path` (the file system path of the module) and `module.name` (the configured name).

With this configuration, `qik lint` will run three separate commands. By default, subcommands are executed in parallel and cached individually. Use `qik lint -m my_module_a -m module_c` to specify modules.

## Dependencies

Qik has five flavors of dependencies we'll cover: globs, distributions, modules, commands, and constants. At the end, we'll touch on how one can configure global dependencies across all commands.

### Globs

Glob patterns are the heart of qik's dependency structure. We recommend [this documentation](https://git-scm.com/docs/gitignore/en#_pattern_format) for an overview of how to write glob patterns.

Glob patterns are specified as strings in `deps`:

```toml
[command.my_command]
deps = "glob_pattern/**/*.py"
```

### Distributions

Break the cache on a pip distribution change by using the `dist` type of dependency. Here we ensure that we re-run `ruff` linting whenever the `ruff` version changes:

```toml
[command.lint]
exec = "ruff format ."
deps = ["**.py", { type = "dist", name = "ruff" }]
cache = "repo"
```

By default, qik determines the current version of the distribution by examining the activate virtual envirionment. In other words, if you run the command in an environment with a different `ruff` version, the commmand won't be cached.

If using `--watch` mode, qik listens to the actual virtualenv directory for changes, re-invoking the command if the distribution changes. If using `--since`, you must configure where your virtualenv lockfile is located to ensure the command re-runs on changes to the virtualenv:

```toml
[venvs.default]
lock-file = "requirements.txt"
```

### Modules

Depend on a module's files, distributions, and imported files with the `module` type of dependency. Here we run [pyright](https://github.com/microsoft/pyright) type checking modularly based on module changes:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.check_types]
exec = "pyright {module.path}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

If `b_module` imports `a_module`, the cache of both of these will be broken if `a_module` changes.

To use this feature, first ensure you've added `qik.graph` to `plugins`:

```toml
plugins = ["qik.graph"]
```

This plugin adds commands that build, analyze, and cache the import graph in the repo. Also remember to install the optional graph dependencies with `pip install "qik[graph]"` (note that these are included with `qik[dev]`).

Imports inside of `TYPE_CHECKING` blocks will be included, along with third-party distributions. To disable this behavior:

```toml
[graph]
include-type-checking: false
include-dists: false
```

### Commands

Use a command as a dependency to force ordering in parallel runs. For example, code formatters that edit Python files should be considered as dependent commands to avoid race conditions.

Here we run type checking after code formatting:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.format]
exec = "ruff format {module.path}"
deps = ["{module.path}/**.py"]
cache = "repo"

[commands.check_types]
exec = "pyright {module.path}"
deps = [
    {type = "module", name = "{module.name}"},
    {type = "command", name = "format"}
]
cache = "repo"
```

When running `qik check_types`, the `format` command will also be selected for runs. This can be disabled by supplying `--isolated` to the command runner.

#### Strict Command Dependencies

When running commands with `--since` or `--watch`, one can ensure downstream dependent commands are invoked by making a *strict* command dependency.

For example, say that we have a modular test runner and a coverage report command:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.test]
exec = "pytest {module.path}"
deps = [{ type = "module", name = "{module.name}" }]

[commands.coverage]
exec = "coverage report"
deps = [{ type = "command", name = "test", strict = true}]
```

With `strict = true`, if we `--watch` or use `--since` in the command runner, we ensure that `coverage` is also executed if `test` is executed.

#### Isolated Command Dependencies

By default, qik runs dependent upstream commands. For example, `qik run coverage` will also run the test suite. This can be disabled globally with `qik run coverage --isolated`.

Command dependencies can also specify `isolated` when needed:

- `isolated = false` ensures the dependent command is always selected, even if the user uses `--isolated`.
- `isolated = true` ensures the user must select the upstream command. For example, `qik coverage` would not run testing, but `qik coverage test` would run both of them and still guarantee execution order.

### Constants

Use a constant value as a dependency and break the cache by changing it:

```toml
[commands.my_command]
deps = [{ type = "const", val = "value" }]
```

As we will show later, using a constant value as a global dependency can aid in manually breaking the cache for everything.

!!! note

    Unless working with dynamic variables such as [qik context](context.md), putting constants in a separate file and dependening on this file is preferred. This ensures a more granular results when using `--since` or `--watch`.

### Global Dependencies

Configure `deps` at the root of your `qik.toml` for global dependencies. For example, here we configure our `.python_version` file as a global dependency, ensuring all of our commands re-run if we update our python version:

```toml
deps = [".python_version"]

[command.lint]
...
```