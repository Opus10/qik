# Spaces

Qik *spaces* form the foundation of command isolation and parametrization. We discuss these concepts here and describe how commands and plugins leverage spaces.

We assume the reader is familiar with virtual environments. Here we are specifically referring to [Python virtualenvs]() for now, although the concept can extend to any virtualenv manager ([conda](), [npm](), etc).

## The Default Space

Qik always uses a space when executing a command. If a space isn't specified, the *default* space is used, which defaults to the active virtualenv and environment variables unless overridden in `qik.toml`.

Some features of qik, such as the `--since` flag, may require you to configure the default space to have requirements. The default space can be overridden like so:

```toml
[spaces.default]
venv = "requirements.txt"
```

## Virtual Environments

### Default Behavior

By default, qik does not manage or activate a virtualenv. Commands are executed in whichever virtualenv is active. This holds true even when one overrides the requirements file as show above.

Adding a requirements file, however, does cause this file to be a dependency for commands, ensuring caches are broken if the requirements change.

### Configuration

Configure a virtualenv directly with just its requirements file. An entire space can be configured with just a requirements file too:

```toml
[spaces]
my-space = "my_space_requirements.txt"
```

All virtualenvs have these core properties:

- `reqs`: A file (or files) of requirements.
- `lock`: An optional lock file.

The more verbose configuration of the above example looks like this:

```toml
[spaces.my-space]
venv = {type = "active", reqs = "my_space_requirements.txt"}
```

Virtualenvs can be inherited when using multiple spaces:

```toml
[spaces.default]
venv = "requirements.txt"

[spaces.other]
venv = [{type = "space", name = "default"}]
```

### Locking and Installation

Qik leaves locking and installation to virtualenv plugins. When using one, keep the following in mind:

- The type of virtualenv will default to what's provided by the plugin. One must verbosely configure the `type` to pick the `active` virtualenv.
- Plugins often dynamically introduce dependencies to commands. For example, the [UV plugin](plugin_uv.md) adds the lock file and the locking/installation commands as dependencies for any command that runs in a UV virtualenv.

### Advanced Configuration

See the [UV docs](plugin_uv.md) for examples on how to manage the Python version and apply global dependency constraints across all virtualenvs using [UV](https://github.com/astral-sh/uv).

## Dotenv Files

Spaces also support dotenv files using the `dotenv` attribute:

```toml
[spaces.my-space]
dotenv = ["my_dotenv.env", "my_other_dotenv.env"]
```

When using a `dotenv` file or files, keep the following hierarchy in mind:

- The current process env is the starting point.
- The virtual env changes, such as the `PATH`, are applied next.
- Environment variables from any `dotenv` file are applied in order of configuration.

## Modules and Command Parametrization

Spaces can configure a list of `modules`, for example:

```toml
[spaces.my-space]
modules = ["my_module", "my_other_module"]
```

Modules may be directly used to parametrize commands:

```toml
[commands.parametrized-command]
exec = "pytest {module.dir}"
```

Parametrized commands are executed across all modules in all spaces unless a space is specified in the command definition. We touch more on module parametrization in the [commands](commands.md) docs.

Modules have the following attributes:

- `dir`: The file system directory of the module.
- `pyimport`: The dotted Python import path.

Remember, modules are paths. A nested module looks like this:

```toml
[spaces.my-space]
modules = ["my/nested/module"]
```

Modules can be re-named, which affects their namespace and other behavior in qik:

```toml
[spaces.my-space]
modules = [{name = "module_name", path = "my/nested/module"}]
```

!!! remember

    Modules are owned by spaces and cannot be shared.

## Fences

Plugins such as [Pygraph](plugin_pygraph.md) leverage the `fence` of a space. A fence is an internal boundary for this space.

By default, the `fence` is turned off, ensuring plugins don't do fence-specific commands on the space. To use the default fence of just the modules, do `fence = true`:

```toml
[spaces.my-space]
modules = ["path/to/module_one"]
fence = true
```

To extend the fence around the modules, add globs:

```toml
[spaces.my-space]
modules = ["path/to/module_one"]
fence = ["other/path"]
```

Fences can also be extended to other spaces:

```toml
[spaces.default]
fence = ["primary/area"]

[spaces.my-space]
modules = ["path/to/module_one"]
fence = ["other/path", {type = "space", name = "default"}]
```

The fence of `my-space` includes `path/to/module_one`, `other/path`, and `primary/area`.

To recap, fences help plugins understand the boundary of a space. See the [Pygraph plugin docs](plugin_pygraph.md) for a practical example of how fences are used for import linting.

Other plugins can build on this concept, for example, creating an optimized docker container for a space in a monorepo.

## Roots

Specify a `root` in a space to enhance other aspects of qik:

```toml
[spaces.my-space]
root = "my/space"
```

When a root is configured like above, changing into any directory under `my/space` will alter the behavior of `qik`, ensuring only commands in this space are selected. Similarly, `qikx` uses the working space as the default.

Remember, roots cannot be children of others. Roots are best when working across a flat hierarchy of a large project that may have separate web apps, modules, frontends, backends, etc.

## Command Line Interaction

Keep the following in mind when using the `qik` command line tool:

- Use `-s` to select commands based on spaces. The argument can be used repeatedly to specify multiple spaces.
- The `-s` flag defaults to the current working space if a `root` is defined.

The `qikx` utility has the following behavior:

- Use `qikx command@space_name --arg1 value1 --arg2 value2` to run an arbitrary executable in a space.
- Similar to `qik`, the current working space is used if a `root` is defined.
