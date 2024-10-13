# Spaces

Qik *spaces* form the foundation of command isolation and parametrization. We discuss these concepts at a high level and describe how commands and plugins leverage them.

## Defining a Space

A space consists of the following optional attributes:

- A virtual environment (or *virtualenv*) for isolating tools and libraries.
- Dotenv files for configuring environment variables.
- Modules for parametrizing commands.
- A fence for isolating a section of the monorepo.
- A root for defining the working directory.

Spaces can be configured in `qik.toml` by just a virtualenv requirements file:

```toml
[spaces]
my-space = "requirements.txt"
```

Or more verbosely configured:

```toml
[spaces.my-space]
venv = {type = "active", reqs = "requirements.txt"}
dotenv = ["my_dotenv.env", "my_other_dotenv.env"]
modules = ["my/nested/module"]
fence = ["other/path"]
root = "my/space"
```

!!! note

    If spaces aren't configured, qik uses the *default* space, which is your active environment. In other words, all executables available in your shell can be ran as qik commands.

## Virtual Environments

### How it Works

By default, qik does not manage or activate virtual environments when running commands. Plugins like [UV](plugin_uv.md) enable this functionality.

Some features of qik, such as the `--since` flag, may still require you to configure a requirements file for the default space if not using a virtualenv plugin:

```toml
[spaces.default]
venv = "requirements.txt"
```

When doing this, the requirements file is added as a dependency for every command in the space, ensuring caches are busted when the requirements change.

Plugins like [UV](plugin_uv.md) also inject dependencies to ensure the virtualenv is installed before running the command inside it.

### Configuration

See the [UV plugin docs](plugin_uv.md) for in-depth examples of configuring virtualenvs. We cover a few basics for all virtualenv plugins here.

First, all have these core properties:

- `reqs`: A file (or files) of requirements.
- `lock`: An optional lock file.

Virtualenvs can be configured directly with just the requirements file:

```toml
[spaces.my-space]
venv = "my_space_requirements.txt"
```

The type of virtualenv defaults to the active virtualenv plugin. This attribute still must be specified directly for verbose configuration:

```toml
[spaces.my-space]
venv = {type = "uv", reqs = "my_space_requirements.txt"}
```

Finally, virtualenvs can be inherited from other spaces:

```toml
[spaces.default]
venv = "requirements.txt"

[spaces.other]
venv = [{type = "space", name = "default"}]
```

!!! tip

    See the [last section on default configuration](#default-configuration) to set a default virtualenv for all spaces.

<a id="dotenv"></a>
## Dotenv Files

Spaces support [dotenv files](https://hexdocs.pm/dotenvy/dotenv-file-format.html) using the `dotenv` attribute:

```toml
[spaces.my-space]
dotenv = ["my_dotenv.env", "my_other_dotenv.env"]
```

When using a `dotenv` file or files, keep the following hierarchy in mind:

- The current process env is the starting point.
- The virtual env changes, such as the `PATH`, are applied next.
- Environment variables from any `dotenv` file are applied in order of configuration.

<a id="modules"></a>

## Modules and Command Parametrization

Spaces can configure a list of `modules`, which are paths relative to `qik.toml`. For example:

```toml
[spaces.my-space]
modules = ["my_module", "my/nested/module"]
```

The `dir` and `pyimport` attributes of modules can be used to parametrize commands:

```toml
[commands.parametrized-command]
exec = "pytest {module.dir}"
```

We touch more on module parametrization in the [command docs](commands.md).

Modules can be re-named, which affects their namespace and other behavior in qik:

```toml
[spaces.my-space]
modules = [{name = "module_name", path = "my/nested/module"}]
```

!!! remember

    Modules are owned by spaces and cannot be shared.

<a id="fences">

## Fences

Plugins such as [Pygraph](plugin_pygraph.md) leverage the `fence` of a space, which is an enclosure of directories in a project.

By default, the `fence` is disabled. Use `fence = true` to enclose only the modules:

```toml
[spaces.my-space]
modules = ["path/to/module_one"]
fence = true
```

Extend this fence with additional directories:

```toml
[spaces.my-space]
modules = ["path/to/module_one"]
fence = ["other/path"]
```

Fences can recursively include other spaces:

```toml
[spaces.default]
fence = ["primary/area"]

[spaces.my-space]
modules = ["path/to/module_one"]
fence = ["other/path", {type = "space", name = "default"}]
```

The fence of `my-space` includes `path/to/module_one`, `other/path`, and `primary/area`.

To recap, fences help plugins understand the boundary of a space. See the [Pygraph plugin docs](plugin_pygraph.md) for a practical example of how fences are used for import linting.

Other plugins can build on this concept, for example, creating an optimized docker container based on files in a project.

## Freeform Commands with `qikx`

The `qikx` utility can be used to run arbitrary executables in a space. For example, say we have the following space:

```toml
[spaces.my-space]
venv = "requirements.txt"
```

`qikx pytest@my-space arg1 arg2 --flag` will run `pytest arg1 arg2 --flag` in the virtualenv of `my-space`. One can specify the `root` of the space as shown below to avoid the `@` syntax.

!!! tip

    Use `qikx --install` to sync all virtualenvs, which are not installed by default.

## Roots

Specify a `root` to set a working directory for a space:

```toml
[spaces.my-space]
root = "my/space"
```

Changing into any directory under `my/space` will alter the behavior of `qik`, ensuring only commands in this space are selected. Similarly, `qikx` uses the space with the closest `root` as the default.

!!! remember

    Roots cannot be children of others and are intended to separate a project into a flat hierarchy.

## Command Line Interaction

When using the `qik` command line tool:

- Use `-s` to select commands based on a space or multiple spaces.
- The `-s` flag defaults to the current working space if a `root` is defined.

The `qikx` utility has the following behavior:

- Use `qikx command@space_name --arg1 value1 --arg2 value2` to run an arbitrary executable in a space.
- Similar to `qik`, the current working space is used if a `root` is defined.

## Default Configuration

Qik supports configuring a default virtualenv and dotenv that will be applied to all spaces if not overridden:

```toml
[defaults]
venv = "requirements.txt"
dotenv = ["my_dotenv.env", "my_other_dotenv.env"]
```
