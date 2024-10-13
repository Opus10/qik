# Space Examples

Here we cover examples of how spaces can be used independently of qik [commands](commands.md) for problems such as environment management and import linting.

For the command examples, see [this cookbook section](cookbook_commands.md).

## Virtual Environments

#### Constrained envs with UV

Constrain all environments by a global constraint file:

```toml
[plugins.uv]
pyimport = "qik.uv"
constraint = "lock.txt"

[spaces.default]
venv = {type = "uv", reqs = "reqs.in", lock = "lock.txt", constraint = ""}

[spaces.module-one]
venv = "module_one/reqs.in"

[spaces.module-two]
venv = "module_two/reqs.in"
```

Above, our default space has all main requirements and a lock file stored at `lock.txt`. Each module has broad requirements that are constrained by the lock of the main virtual environment.

This strategy can be useful for testing modules in isolated virtual environments against the versions of dependencies that will be used in production.

!!! warning

    This is a chicken-and-egg problem. If you haven't yet generated your main lock file, create an empty one before running `qik uv.lock`.

#### Using `qikx` with space roots for directory-based environments

If your monorepo has multiple projects or multiple standalone modules, provide a `root` for each space and use `qikx` to run commands:

```toml
[plugins]
uv = "qik.uv"

[spaces.module-one]
root = "module_one"
venv = "module-reqs.txt

[spaces.project-one]
root = "project_one"
venv = "app-reqs.txt"
```

Now you can `cd` into `module_one/` and run `qikx executable arg --flag` to run executable with arbitrary arguments within the virtual environmet of your `module-one` space. This same concept also applies to dotenv files of a space.

!!! tip

    Use `qikx --install` to sync all virtualenvs, which are not installed by default.

## Fences

#### Linting imports with Pygraph

Here we have a project with the following modules:

```
foo/
bar/
baz/
```

We can configure fences and use the [Pygraph plugin](plugin_pygraph.md) to ensure each of these modules has the following properties:

- `foo` has no internal dependencies.
- `bar` can import `foo`.
- `baz` can import `bar` and any of its internal dependencies.

```toml
[plugins]
pygraph = "qik.pygraph"

[spaces.foo]
fence = ["foo"]

[spaces.bar]
fence = ["bar", {type = "space", name = "foo"}]

[spaces.baz]
fence = ["bar", {type = "space", name = "bar"}]
```

By including the fences of other spaces in our `fence` definition, we ensure that `baz` is able to import anything that the `bar` module is able to import, similar to how external PyPI dependencies work.

Running `qik pygraph.check` will show any import violations.

!!! tip

    Set a `venv` for each space to restrict third party imports, otherwise the active virtual environment will be checked.
