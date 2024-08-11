# Context

Some commands need configurable or environment-based parameters, either as dependencies or in the command executable. This is where qik context comes in.

## The Basics

Add `vars` to `qik.toml` to define a context variable:

```toml
vars = ["my_var"]
```

Variables are available in the `{ctx}` variable, which is fully available in command definitions and available in most other configuration blocks (caches, virtual environments, etc).

Root-level variables in `qik.toml` are available under the *project* namespace. For example, let's echo our variable in a command:

```toml
vars = ["my_var"]

[commands.my_var_command]
exec = 'echo "var={ctx.project.my_var}"'
```

Variables have the following additional options:

- `required`: Defaults to `True`. If `False`, references return `None`, otherwise a runtime error is raised.
- `type`: Defaults to `str`. Can be `int` or `bool`. Improper toml types result in a runtime error.
- `default`: Defaults to `None`.

For example, here we define an integer variable that defaults to 100:

```toml
vars = [{name = "my_int_var", type = "int", default = 100}]
```

## Setting Context

Running `qik my_var_command` will result in an error - `No value supplied for "project.my_var" ctx.`. There are several ways to set context variables:

1. Providing a default value to the variable definition.
2. Configuring a context profile.
3. In the environment.

### Default Values

Set a default value like so:

```toml
vars = [{name = "my_var", default = "hi"}]
```

Running `qik my_var_command` will print `var=hi`.

!!! note

    Variables can be marked as `required = false`, resulting in the command printing `var=None`.

### Context Profiles

Defaults can be overridden with context *profiles*:

```toml
[ctx.default.project]
my-var = "hello"
```

Above we've set the variable in the default profile for the *project* namespace. Running `qik my_var_command` will print `var=hello`.

!!! remember

    All context variables are *kebab* case when referencing them as keys in toml.

To avoid overriding the default profile:

```toml
[ctx.custom.project]
my-var = "hello"
```

Use `-p` to reference the `custom` profile:

```bash
qik my_var_command -p custom
```

The above invocation will print `var=hello`. Without `-p`, we'll use the variable default, printing `var=hi`.

!!! tip

    Set the profile with the `QIK__PROFILE` environment variable.

### Environment

Environment variables override profiles or default values. They follow the naming convention of `{NAMESPACE}__{VAR}`. For example:

```bash
PROJECT__MY_VAR="hello world" qik my_var_command -p custom
```

The above will print `var=hello world`, overriding both profiles and default values.

!!! note

    Environment variables must be propertly typed, otherwise a runtime error is raised. Valid boolean environment variables are `yes`, `true`, `1`, `no`, `false`, and `0` (case insensitive).

## Qik Runtime Context

Runtime context, such as the architecture, selectors, workers, and default cache, can be set in the *qik* namespace. Let's start with the following configuration:

```toml
[commands.hello]
exec = "echo '{ctx.qik.arch}'"
```

Above we're printing the architecture of the machine, defaulting to one of `win-64`, `win-32`, `linux-64`,`linux-aarch64`, `linux-ppc64le`, `linux-32`, `osx-arm64`, `osx-64`.

We can override the architecture or any qik runtime configuration with environment variables or profiles:

```bash
QIK__WORKERS=1 QIK__ARCH=custom_arch qik hello
```

Above, we'll use only one worker and print our `custom_arch` string as the architecture. Similar to project-level context, we can override qik context in profiles:

```toml
[ctx.default.qik]
workers = 3
force = true
verbosity = 2
```

Here's a list of all qik context variables:

| Name | Default | Description |
| ---- | ------- | ----------- |
| isolated | `True` | Run isolated commands (`--isolated`) |
| watch | `False` | Watch commands (`--watch`) |
| cache | `None` | Set the default cache (`--cache`) |
| force | `False` | Break the cache (`-f`) |
| ls | `False` | List commands (`--ls`) |
| workers | *thread count* | Set the number of workers (`-n`) |
| fail | `False` | Fail if no commands are selected (`--fail`) |
| cache_when | `success` | Set when to cache (`--cache-when`) |
| since | `None` | Select commands since git reference (`--since`) |
| commands | `None` | The default commands to run when none are provided to `qik` |
| modules | `None` | The default modules (`-m`) |
| cache_status | `None` | Select commands by cache status (`--cache-status`) |
| cache_types | `None` | Select commands by cache type (`--cache-type`) |
| arch | *machine arch* | Set the default architecture |

## Using Context in Dependencies

Use the `const` dependency to reference context, for example:

```toml
[commands.pytest]
exec = "pytest"
deps = [{type = "const", val = "{ctx.qik.arch}"}]
```

The above ensures that we break the cache when running on a different architecture.

## Module and Plugin Context

Modules and plugins can also define context in their respective `qik.toml` files. To set or reference a module's context in the root `qik.toml`, use the *modules* namespace. Use the *plugins* namespace for plugin context.

For example, say we have this `qik.toml` in `my/module/path`:

```qik
vars = ["my_module_var"]

[commands.print_var]
exec = "echo '{ctx.modules.my.module.path.my_module_var}'"
```

In the root `qik.toml`, we can set it in a profile:

```toml
modules = ["my.module.path"]

[ctx.default.modules.my.module.path]
my-module-var = "var is set"
```

Running `qik my.module.path.print_var` will show `var is set`.

!!! remember

    [Using a module alias](commands.md#alias) can help decrease the verbosity for nested paths.

## Recap

Qik context allows for dynamic variables in `qik.toml`. These variables can be overridden by environment variables or by configuring different runtime profiles.

There are four namespaces: *project* for root-level variables, *qik* for qik runtime variables, *modules* for variables defined in modules, and *plugins* for variables defined in plugins. Environment variables named `{NAMESPACE}__{VARIABLE}` can be used to override any variable.
