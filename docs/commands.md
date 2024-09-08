# Commands

Commands are the core construct of qik. Here we discuss configuration, modular commands, dependencies, and using the command runner.

## Configuration

Commands are shell strings configured in `qik.toml`, which can live at the root of your project or a subdirectory:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
```

Commands are executed with `qik <cmd> <cmd>` (or `qik` for all commands). Shell strings are executed in the current working directory of your `qik.toml`.

To leverage command caching, add `deps` (dependencies) and a `cache`:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Running `qik lock` will cache results of this command in your git repo. The cache is broken if `requirements.in` changes.

Use a `local` cache to cache results locally or specify `artifacts` to leverage a shared remote cache. See the [caching](caching.md) and [CI/CD](ci.md) sections for an in-depth guide on how to best leverage caching to accomplish your goals.

## Parametrizing Modular Commands

Configure modules and parametrize your commands with them like so:

```toml
modules = ["my_module_a", "nested_module/b", "module_c"]

[command.format]
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

Qik parametrizes any command with `{module}` across all modules. `qik format` will run three invocations of `ruff format` in parallel. Use `qik format -m my_module_a -m nested_module/b` to run specific modules.

We'll cover more advanced module configuration later. For now keep the following in mind:

- `modules` is a list of paths, using `/` as the directory separator.
- Use `modules = [{ name = "name", path = "path/to/folder"}]` to give the module a different name (alphanumeric characters, dots, or underscores only).
- Use `{module.dir}` for the directory or `{module.imp}` for the dotted import path.

## Dependencies

Qik command caching is centered around a rich set of dependencies. Here we'll cover globs, distributions, modules, commands, and constants. At the end, we'll touch on global dependencies across all commands.

For a more in-depth look into how dependency caching works, see [the caching section](caching.md).

### Globs

Glob patterns are specified as strings in `deps` and relative to the location of your `qik.toml`. We recommend [this documentation](https://git-scm.com/docs/gitignore/en#_pattern_format) for an overview of acceptable glob patterns:

```toml
[command.my_command]
deps = ["dir/**/*.py"]
```

<a id="distributions"></a>

### Distributions

Use the `dist` dependency type to depend on an external Python distribution. Qik examines the virtual environment to break the cache if the version changes. Here we depend on the `ruff` distribution:

```toml
[command.lint]
exec = "ruff format ."
deps = ["**.py", {type = "dist", name = "ruff"}]
cache = "repo"
```

### Modules

Use the `module` dependency type to depend on a module's files, import graph, and external distributions. Here we run [pyright](https://github.com/microsoft/pyright) type checking modularly based on module changes:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.graph"]

[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

If `b_module` imports `a_module`, we'll re-run type checking on both if `a_module` changes.

Above we've added `qik.graph` to plugins. Doing `qik --ls` will show two additional graph commands that are automatically used to build and analyze the import graph. See [this section](#module) for more information on how to configure module dependencies.

!!! remember

    Install optional graph dependencies with `pip install "qik[graph]"`. These are automatically included in `qik[dev]`.

### Commands

Use commands as a dependency to force ordering. For example, code formatters that edit Python files should be ran before other commands that analyze them. Here we run type checking after code formatting:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.pygraph"]

[commands.format]
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"

[commands.check-types]
exec = "pyright {module.dir}"
deps = [
    {type = "pygraph", imp = "{module.imp}"},
    {type = "command", name = "format"}
]
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

<a id="global"></a>

### Global Dependencies

Configure `deps` at the root of your `qik.toml` for global dependencies. For example, here we configure our `.python_version` file as a global dependency, ensuring all of our commands re-run if we update our python version:

```toml
deps = [".python_version"]

[command.lint]
...
```

<a id="runner"></a>

## The Command Runner

### Basic Usage

Use `qik` to run all commands or `qik <cmd_name> <cmd_name>` to run a list of commands. For modular commands, use `-m` to pass specific modules.

By default, commands are executed across all threads. Use `-n` to adjust the number of workers.

### Output

When running serially (i.e. `-n 1`) or invoking a single runnable, qik displays all output. The :fast_forward: emoji indicates a cached run while :construction: indicates uncached.

Parallel runs show progress bars for all commands followed by error output. Show no output with `-v 0` or full output with `-v 2`.

In all circumstances, the output of the most recent run is always available in the `._qik/out` directory. Tail the files from this directory to see progress on long-running commands.

### Watching for Changes

Use `--watch` to reactively re-run commands based on file changes. For `dist` dependencies, qik will watch the virtual environment for modifications.

### Isolated Commands

Running a command with a dependent command will also bring it into the executable graph. For example, `qik lint` will also run `format` if `lint` depends on `format`. Use `--isolated` to ignore command dependencies.

!!! note

    Commands can override this by specifying `isolated=True` in their dependency defintion. We explain command dependencies in detail [here](#command).

### Selecting Since a Git Reference

Use `--since` to select commands based on changes since a git SHA, branch, tag, or other reference.

If using `dist` dependencies, be sure to configure the location of the default virtual environment lock file:

```toml
[venvs.default]
lock-file = "requirements.txt"
```

### Setting the Default Cache and Cache Behavior

Use `-f` to break configured caches. Use `--cache` to set a default cache for commands that don't have one. Use `--cache-when` to configure the default behavior of when commands are cached. See the [caching section](caching.md) for more information on what this means.

### Selecting Based on Cache Type or Status

Use `--cache-type` to select commands based on the type of cache, such as `local`, `repo`, or a [custom remote cache you've defined](caching.md#s3).

Select commands that have a warm or cold cache with `--cache-status warm` or `--cache-status cold`.

Combinations of these selectors are beneficial for CI/CD optimizations. See the [CI/CD](ci.md) section for more information.

### Listing and Failing

Use `--ls` with any `qik ...` command to see which runnables are selected without running them. Supplying `--fail` will return a non-zero exit code if any commands are selected.

Similar to the cache selectors, `--fail` can be beneficial for [CI/CD integration](ci.md).

### Setting the Context Profile

Set the context profile with `-p`. More on [qik context here](context.md).

## Advanced Configuration

Some aspects of the command runner and runnable graph have advanced configuration parameters that we discuss here.

<a id="module"></a>

### Import Graph Dependencies

When depending on a python module, any import, even inside of a `TYPE_CHECKING` block, will be included in the dependency graph. Similarly, any direct third-party import will be included as a distribution dependency. Disable this behavior with the `pygraph` config section:

```toml
[pygraph]
ignore-type-checking = true
ignore-dists = true
```

!!! note

    Optional distributions that aren't installed in the virtual environment may lead to mapping and version resolution errors. See the troubleshooting section on [mapping modules to distributions](errors.md#graph0) and [overriding distribution versions](errors.md#dep0) for more information.

Qik does not discover dynamic imports such as django's [apps.get_model](https://docs.djangoproject.com/en/5.0/ref/applications/#django.apps.AppConfig.get_models). To ensure accuracy in your import graph, do either of:

- Add a standalone file (such as `qikimports.py`) with the non-dynamic imports.
- Do dynamic imports outside of `TYPE_CHECKING`. For example:

    ```
    from typing import TYPE_CHECKING

    from django.apps import apps

    if TYPE_CHECKING:
        # Qik will discover this import
        from my_app.models import MyModel
    else:
        # Do dynamic or lazy importing in the app
        MyModel = apps.get_model("my_app", "MyModel")
    ```

<a id="command"></a>

### Command Dependencies

By default, upstream commands are included in the graph unless using `--isolated`. To ensure a dependenct upstream command is always included, set `isolated = true` in the dependency definition.

Using `--since` or `--watch` will *not* select downstream commands by default if the upstream command is invoked. Change this behavior by configuring the command dependency as *strict*:

```toml
modules = ["a_module", "b_module", "c_module"]
plugins = ["qik.pygraph"]

[commands.test]
exec = "pytest {module.dir}"
deps = [{type = "pygraph", imp = "{module.imp}"}]

[commands.coverage]
exec = "coverage report"
deps = [{type = "command", name = "test", strict = true}]
```

Above, running `qik --watch` or `qik --since` ensures that `coverage` is selected for running if `test` is selected.

As mentioned previously, `--isolated` will ensure `qik coverage` does not select the `test` command. Override this by setting `isolated = false` in the command dependency.

### Using Environment Variables and Machine Architecture

Commands and dependencies can utilize environment variables and machine-specific parameters, providing flexibility in configuring different runtime environments.

See the [qik context section](context.md) for a deep dive on how to do this.

### Commands in Modules

Commands can be defined in `qik.toml` files in project modules. Command names are prefixed by the name of the module.

For example, say we have a root `qik.toml`:

```toml
modules = ["my/module/path"]
```

Then in `my/module/path/qik.toml`:

```toml
[command.my_command]
exec = "echo 'hello world'"
```

`qik --ls` will show a `my/module/path/my_command` command.

<a id="alias"></a>
For deeply-nested paths, consider giving your module an alias:

```toml
modules = [{name = "my_module", path = "my/module/path"}]
```

This command can be executed with `my_module/my_command`.

Keep the following in mind when using defining commands inside modules:

- Glob dependency paths are still relative to the root `qik.toml` directory.
- Use the full aliased name (e.g. `my_module/my_command`) when depending on a module command.
