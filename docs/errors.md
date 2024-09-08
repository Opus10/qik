# Troubleshooting

All errors from the qik CLI. If you encountered an unexpected error, open an issue [here](https://github.com/Opus10/qik/issues).

## General Configuration

<a id="conf0"></a>

#### Config Not Found

`Could not locate qik configuration...` means there is either no `qik.toml` config file or `tool.qik` section in your `pyproject.toml` file.

Remember, the qik config must be present in the same level or a parent of your current working directory.

<a id="conf2"></a>

#### Module Not Found

`Module {name} not configured...` means the module name is not in the configuration file. This can happen when giving a module an alias:

```toml
modules = [{name = "b_module", path = "my.path.to.module.b"}]
```

One must now reference commands in this module with `b_module` or use `b_module` as the module selector (`-m`).

<a id="conf3"></a>

#### Plugin Not Found

`Plugin {name} not configured...` is the same as module not found error from above, but for the `plugins` configuration section.

<a id="conf4"></a>

#### Module or Plugin Not Found

`Module or plugin {name} not configured...` is the same as the module/plugin errors from above. This error happens in qik when looking up objects that are agnostic to being a module or plugin, such as the namespace for a command. They are usually the cause of not being configured or using the wrong alias.

<a id="conf5"></a>

#### Command Not Found

`Command {name} not configured...` means the command name could not be found in the root project configuration or in any `qik.toml` files of modules.

Remember, command names in modules are always referenced as `{module_name_or_alias}.{command_name}`.

<a id="conf6"></a>

#### Plugin Import

`Could not import plugin...` means you likely haven't installed the plugin in the virtual environment.

<a id="conf7"></a>

#### Graph Cycle

`Cycle detected in DAG.` means you have a cycle somewhere in your command definition, for example:

```toml
[commands.one]
exec = 'echo "one"'
deps = [{type = "command", name = "two"}]

[commands.two]
exec = 'echo "two"'
deps = [{type = "command", name = "one"}]
```

## Caching

<a id="cache0"></a>

#### Unconfigured Cache

`Unconfigured cache - "{name}"` means the cache name is not yet configured. Remember that `local` and `repo` caches are provided by qik. Other custom caches must be identified by their name in the project configuration, for example `remote`:

```toml
[caches.remote]
type = "s3"
...
```

<a id="cache1"></a>

#### Invalid Cache Type

`Invalid cache type - "{name}"` means the cache type is not supported by qik or a plugin. For example:

```toml
[caches.remote]
type = "invalid"
...
```

## Context

<a id="ctx0"></a>

#### Context Profile Not Found

`Context profile "{name}" is not configured` means a context profile was not found in the configuration. Qik provides the `default` context profie. Other names must be configured, for example:

```toml
[ctx.custom-profile]
...
```

Use the above profile with `qik -p custom-profile`.

<a id="ctx1"></a>

#### Environment Cast Failure

Context variables are typed, so environment variables must be able to be cast to these types. You'll receive this error when:

- Using an `int` type and a non-integer environment variable.
- Using a `bool` type and an environment variable not in `yes`, `true`, `1`, `no`, `false`, or `0`.

<a id="ctx2"></a>

#### Context Value Not Found

`No value supplied for {context variable name}...` means a required context variable was either not present in configuration or in the environment. See [qik context](context.md) for more information on context variables.

<a id="ctx3"></a>

#### Unconfigured Context

`Ctx {context variable} not configured...` means that context is referenced somewhere in the configuration (e.g. `{ctx.project.variable_name}`) but it hasn't actually been configured. See [qik context](context.md) for configuring context variables.

<a id="ctx4"></a>

#### Invalid Context Namespace

`Ctx namespace {context namespace} is invalid...` means you're accessing context under an invalid namespace. Remember, all context variables must be accessed under the `project`, `qik`, `plugins`, or `modules` namespace, for example `{ctx.qik.num_workers}`.

Similarly, context must be configured under the proper profile and namespace:

```toml
[ctx.default.qik]
...

[ctx.default.project]
...
```

## Virtual Environment

<a id="venv0"></a>

#### Lock File Not Found

`Must configure env lock file (venvs.default.lock-file) when using --since on pydists.` means you're using the `--since` option with `qik` and have a command with `pydist` dependencies. Commands that use module graph dependencies also may depend on python distributions.

To use this functionality with `--since`, qik needs the lock file of the virtual environment. Configure a default like so:

```toml
[venvs.default]
lock-file = "requirements.txt"
```

#### Virtual Environment Not Found

`Venv named "{name}" not configured in qik.venvs` means the referenced virtual environment is not found in the project configuration. Ensure you have a `[venvs.{name}]` section for any non-default virtual environment.

## Graph

<a id="graph0"></a>

#### No Module Distribution

`No distribution found for module "{top-level import}"` means the `qik.pygraph` plugin found an external module that could not be mapped to its PyPI distribution. This can happen when the distribution is not installed in the virtual environment (e.g. optional dependencies) or when issues with Python's `importlib.metadata` arise.

For example, say that `import my_package.submodule` triggers this. You have three options for resolution:

1. Map the top-level module to its distribution:

    ```toml
    [graph.module-pydists]
    my_package = "pypi_distribution"
    ```

    !!! note

        If the distribution is not installed in your virtual environment, you'll also need to configure the distribution version using [this troubleshooting tip](#dep0).

2. Ignore the specific module:

    ```toml
    [graph.module-pydists]
    my_package = ""
    ```

3. Ignore all modules that cannot be mapped:

    ```toml
    [graph]
    ignore-missing-module-pydists = true
    ```

!!! tip

    You can also ignore tracking distributions entirely in the graph with `pygraph.ignore_pydists = true`.

## Dependencies

<a id="dep0"></a>

#### Distribution Not Found

`Distribution "{package name}" not found` means the distribution could not be found in the virtual environment. You have two options for resolution:

1. Map the distribution to a version:

    ```toml
    [pydist-versions]
    pypi-package-name = "version"
    ```

2. Ignore any missing distributions:

    ```toml
    ignore-missing-dists = true
    ```

If this error surfaces from using the `qik.pygraph` plugin for module dependencies, other options for overriding behavior are in [this troubleshooting tip](#graph0).
