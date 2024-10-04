# Context

Some commands need configurable or environment-based parameters, either as dependencies or in the command executable. This is where qik context comes in.

## The Basics

Add `ctx` to `qik.toml` to define a context variable:

```toml
ctx = ["my_var"]
```

Variables are available in the `{ctx}` template variable, which is available in command definitions and most other configuration blocks (caches, virtual environments, etc).

For example, let's echo our variable in a command:

```toml
ctx = ["my_var"]

[commands]
echo-var = 'echo "var={ctx.my_var}"'
```

Running `qik echo-var` will result in an error since the variable has not been defined. Context variables always read from an environment variable with the same name. For example, the following prints "var=hello world":

```bash
MY_VAR="hello world" qik echo-var -n 1
```

## Variable Configuration

Variables have the following additional options:

- `required`: Defaults to `True`. If `False`, references return `None`, otherwise a runtime error is raised.
- `type`: Defaults to `str`. Can be `int` or `bool`. Improper toml types result in a runtime error.
- `default`: Defaults to `None`.

For example, here we define an integer variable that defaults to 100:

```toml
vars = [{name = "my_int_var", type = "int", default = 100}]
```

## Qik Runtime Context

Runtime context, such as the architecture, selectors, workers, and default cache, are set in the *qik* context namespace. For example, here we print the machine architecture:

```toml
[commands]
echo-arch = "echo '{ctx.qik.arch}'"
```

Above we're printing the architecture of the machine, defaulting to one of `win-64`, `win-32`, `linux-64`,`linux-aarch64`, `linux-ppc64le`, `linux-32`, `osx-arm64`, `osx-64`.

Qik context can be overridden with environment variables prefixed by `QIK__`. For example, here we override the number of workers (`-n`) and architecture:

```bash
QIK__WORKERS=1 QIK__ARCH=custom_arch qik echo-arch
```

Here's a list of all qik context variables:

| Name | Default | Description |
| ---- | ------- | ----------- |
| isolated | `True` | Run isolated commands (`--isolated`) |
| watch | `False` | Watch commands (`--watch`) |
| caches | `None` | Select commands by cache(s) (`--cache`) |
| force | `False` | Break the cache (`-f`) |
| ls | `False` | List commands (`--ls`) |
| workers | *thread count* | Set the number of workers (`-n`) |
| fail | `False` | Fail if no commands are selected (`--fail`) |
| since | `None` | Select commands since git reference (`--since`) |
| commands | `None` | Select commands by name |
| modules | `None` | Select commands by space module(s) |
| spaces | `None` | Select commands by spaces |
| cache_status | `None` | Select commands by cache status (`--cache-status`) |
| arch | *machine arch* | Set the default architecture |

## Using Context in Dependencies

Use the `const` dependency to reference context, for example:

```toml
[commands.pytest]
exec = "pytest"
deps = [{type = "const", val = "{ctx.qik.arch}"}]
```

The above ensures that we break the cache when running on a different architecture.
