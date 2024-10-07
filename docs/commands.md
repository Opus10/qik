# Commands

Commands are the core construct of qik. Here we discuss configuration, parametrization, dependencies, the command runner, and more.

## Configuration

Commands are shell strings configured in `qik.toml`. Simple commands can be expressed like so:

```toml
[commands]
lock = "pip-compile > requirements.txt"
```

Commands are executed with `qik <cmd> <cmd>` (or `qik` for all commands). Shell strings are executed in the current working directory of your `qik.toml`.

To leverage command caching, add `deps` (dependencies) and an optional `cache`:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Running `qik lock` will cache results of this command in your git repo. The cache is broken if `requirements.in` changes.

!!! tip

    Dependencies must be tracked indexed in your repo to break the cache. See the [caching guide](caching.md) for an in-depth overview of how caching works. Similarly, see the [CI/CD cookbook](cookbook_cicd.md) for patterns on using caching in continuous integration.

## Dependencies

Qik command caching is centered around a rich set of dependencies. Here we'll cover dependencies provided by the core runner and overview some offered by plugins.

### Globs

Glob patterns are specified as strings in `deps` and relative to the location of your `qik.toml`. See [this documentation](https://git-scm.com/docs/gitignore/en#_pattern_format) for an overview of acceptable glob patterns:

```toml
[command.my_command]
deps = ["dir/**/*.py", "some_file.txt"]
```

<a id="distributions"></a>

### Python Distributions

Use the `pydist` dependency type to depend on an external Python distribution. Qik examines the virtual environment to break the cache if the version changes. Here we depend on the `ruff` distribution:

```toml
[command.lint]
exec = "ruff format ."
deps = ["**.py", {type = "pydist", name = "ruff"}]
cache = "repo"
```

### Commands

Use commands as a dependency to force ordering. Here we run type checking after code formatting:

```toml
[commands.format]
exec = "ruff format ."
deps = ["**.py"]

[commands.check-types]
exec = "pyright ."
deps = ["**.py", {type = "command", name = "format"}]
cache = "repo"
```

There are several ways to configure command dependencies and adjust their runtime behavior that are overviewed in [this section](#command).

<a id="const"></a>

### Constants

Use a constant value as a dependency and break the cache by changing it:

```toml
[commands.my_command]
deps = [{type = "const", val = "value"}]
```

See the [context section](context.md) for using environment variables in constants.

<a id="base"></a>

### Base Dependencies

Configure `base.deps` for base dependencies. For example, here we configure our `.python_version` file as a base dependency, ensuring all of our commands re-run if we update this file:

```toml
[base]
deps = [".python_version"]

[command.lint]
...
```

### Python Import Graph

Use the `pygraph` plugin to depend on a Python module's files, import graph, and external distributions. Here we run [pyright](https://github.com/microsoft/pyright) type checking over a module and its import graph:

```toml
[plugins]
pygraph = "qik.pygraph"

[commands.check-types]
exec = "pyright my/module"
deps = [{type = "pygraph", pyimport = "my.module"}]
cache = "repo"
```

See the [Pygraph plugin docs](plugin_pygraph.md) for a comprehensive overview of installing, configuring, and using this dependency type.

## Spaces

### Assigning a Space

By default, commands run in the *default* space. Assign a space like so:

```toml
[plugins]
uv = "qik.uv"

[spaces.my-space]
venv = "ruff-requirements.txt"

[command.lint]
exec = "ruff format ."
space = "my-space"
```

Above we ensure `qik lint` runs ruff formatting in `my-space`. We use the [UV plugin](plugin_uv.md) to lock and install the virtualenv.

!!! tip

    Use `qik -s my-space` to only select commands in the `my-space` space.

<a id="parametrized-commands"></a>

### Parametrizing Commands

Provide a `{module}` string in your executable to parametrize commands over [space modules](spaces.md#modules):

```toml
[spaces.default]
modules = ["my_module_a", "nested_module/b", "module_c"]

[command.format]
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py"]
```

`qik format` will run three invocations of `ruff format` in parallel

Remember, the `{module}` variable has two key attributes:

1. `dir` for the relative directory to `qik.toml`.
2. `pyimport` for the dotted Python import path.

!!! tip

    Use `qik format -m my_module_a -m nested_module.b` to run specific modules.

<a id="runner"></a>

## The Command Runner

### Basic Usage

Use `qik` to run all commands or `qik <cmd_name> <cmd_name>` to run a list of commands. For modular commands, use `-m` to pass specific modules.

By default, commands are executed across all threads. Use `-n` to adjust the number of workers.

### Output

When running serially (i.e. `-n 1`) or invoking a single runnable, qik displays all output. The :fast_forward: emoji indicates a cached run while :construction: indicates uncached.

Parallel runs show progress bars for all commands followed by error output. Show no output with `-v 0` or full output with `-v 2`.

In all circumstances, the output of the most recent run is always available in the `._qik/out` directory. Tail the files from this directory to see progress on long-running commands.

!!! note

    We are working on better ways to show output across multiple long-running commands. See our [roadmap](roadmap.md) for more information.

### Watching for Changes

Use `--watch` to reactively re-run commands based on file changes. For `pydist` dependencies, qik will watch the virtual environment for modifications.

### Isolated Commands

Running a command with a dependent command will also bring it into the executable graph. For example, `qik lint` will also run `format` if `lint` depends on `format`. Use `--isolated` to ignore command dependencies.

!!! note

    Commands can override this by specifying `isolated=True` in their dependency defintion. We explain command dependencies in detail [here](#command).

### Selecting Since a Git Reference

Use `--since` to select commands based on changes since a git SHA, branch, tag, or other reference.

If using `pydist` dependencies without a virtualenv plugin, be sure to configure the location of the default requirements or lock file:

```toml
[spaces.default]
venv = "requirements.txt"
```

### Breaking the Cache

Use `-f` to run commands without using the cache.

### Listing and Failing

Use `--ls` with any `qik ...` command to see which runnables are selected without running them. Supplying `--fail` will return a non-zero exit code if any commands are selected.

### Selecting Based on Cache Properties

Use `--cache` to select commands based on the cache, such as `local`, `repo`, or a [custom remote cache you've defined](caching.md#s3).

Select commands that have a warm or cold cache with `--cache-status warm` or `--cache-status cold`.

!!! tip

    Combinations of these selectors, including `--ls` and `--fail`, are beneficial for CI/CD optimizations. See the [CI/CD](cookbook_cicd.md) section for more information.

## Advanced Configuration

Some aspects of commands, the runner, and dependencies have advanced configuration parameters that we discuss here.

<a id="command"></a>

### Command Dependencies

Using `--since` or `--watch` will *not* select downstream commands by default if the upstream command is invoked. Change this behavior by configuring the command dependency as *strict*:

```toml
[commands.test]
exec = "pytest ."
deps = ["**.py"]

[commands.coverage]
exec = "coverage report"
deps = [{type = "command", name = "test", strict = true}]
```

Above, running `qik --watch` or `qik --since` ensures that `coverage` is selected for running if `test` is selected.

By default, upstream commands are included in the graph unless using `--isolated`. To ensure a dependent upstream command is always included, set `isolated = false` in the dependency definition.

### Using Environment Variables and Machine Architecture

Commands and dependencies can utilize environment variables and machine-specific parameters, providing flexibility in configuring different runtime environments.

See the [qik context section](context.md) for a deep dive on how to do this.

### Custom Python Paths

Some projects may have a non-standard Python path. For example, having a root path for a Python backend:

```
qik.toml
frontend/...
backend/...
```

The default Python path is always where the root `qik.toml` presides. Override the default python path like so:

```toml
[defaults]
python-path = "backend"
```

Keep the following in mind:

- Paths to modules, such as `[spaces.modules]` are still relative to the root `qik.toml`, i.e. `backend/my/module`.
- Python import paths are relative to the python path, i.e. `my.module`.

### Pydist Dependencies

Sometimes a `pydist` type of dependency may not be available in your virtual environment. You have two configuration options at your disposal:

1. Set `[pydist.versions]` in your `qik.toml`:

    ```toml
    [pydist.versions]
    dist-name = "0.1.0"
    ```

2. Ignore missing pydists with `[pydist.ignore_missing]`:

    ```toml
    [pydist]
    ignore_missing = true
    ```

Keep in mind that both of these are global settings that will apply if a pydist version cannot be found in the virtual environment.

!!! note

    Toml syntax requires `kebab` casing. For example, a pydist of `my_dist` would still need to be named `my-dist`. This is not impactful because of how dist names are normalized.

### Pygraph Dependencies

Dependencies on Python import graphs can be configured and overridden in a number of ways. See the [Pygraph plugin docs](plugin_pygraph.md) for a comprehensive overview.

### Module Commands

Commands can be defined in a [space module's qik.toml file](spaces.md#modules). Command names are prefixed by the module name.

For example, in `my/module/path/qik.toml`:

```toml
[command.my_command]
exec = "echo 'hello world'"
```

If we have a space like this:

```toml
[spaces.default]
modules = ["my/module/path"]
```

`qik --ls` will show a `my/module/path/my_command` command.

<a id="alias"></a>
For deeply-nested paths, consider giving your module an alias:

```toml
[spaces.default]
modules = [{name = "my_module", path = "my/module/path"}]
```

This command can be executed with `my_module/my_command`.

Keep the following in mind when using defining commands inside modules:

- Glob dependency paths are still relative to the root `qik.toml` directory.
- Spaces must be defined in the root `qik.toml`.
- Use the full aliased name (e.g. `my_module/my_command`) when depending on a module command.
