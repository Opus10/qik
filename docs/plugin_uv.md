# UV

The UV plugin provides [UV virtual environments](https://github.com/astral-sh/uv) for qik commands. We overview installation, configuration, and advanced usage here.

## Installation

The UV plugin requires additional dependencies. `pip install "qik[dev]"` to get all dev dependencies including uv. Otherwise, `pip install "qik[uv]"`.

!!! note

    One can manually install `uv` too.

After this, configure the plugin in `qik.toml`:

```toml
[plugins]
uv = "qik.uv"
```

## Usage

### Basic Configuration

Once the plugin is installed and added to `[plugins]`, UV will be the default virtual env manager. Create a space with a requirements file like so:

```toml
[plugins]
uv = "qik.uv"

[spaces]
default = "requirements.txt"
```

or more verbosely:

```toml
[plugins]
uv = "qik.uv"

[spaces.default]
venv = "requirements.txt"
```

Running a command within the space will lock and install the virtual environment beforehand.

### Lock Files

Lock file artifacts are stored in the repo cache by default, i.e. `.qik/artifacts`. Override this by setting `[plugins.uv.cache]` to a different one.

The lock file path can be directly specified:

```toml
[spaces.default]
venv = {type = "uv", reqs = "requirements.txt", lock = "requirements.lock"}
```

Lock files are universal across platforms by default.

### Constraints

Configure a [constraint file](https://docs.astral.sh/uv/pip/compile/#adding-constraints) to keep dependencies of spaces constrained. This can be done globally in the plugin config:

```toml
[plugins.uv]
pyimport = "qik.uv"
constraint = "constraints.txt"
```

Or per space:

```toml
[spaces.default]
venv = {type = "uv", reqs = "requirements.txt", constraint = "constraints.txt"}
```

### Python Version

By default, the virtualenv uses the active Python version. Utilize UV's Python version management by configuring `python` to the proper version. This can be done globally in the plugin config:

```toml
[plugins.uv]
pyimport = "qik.uv"
python = "3.12"
```

Or per space:

```toml
[spaces.default]
venv = {type = "uv", reqs = "requirements.txt", python = "3.12"}
```

### Custom Index URLs

Configure a custom index URL or extra index URL in the plugin config:

```toml
[plugins.uv]
pyimport = "qik.uv"
index-url = "https://my-index-url.com"
extra-index-url = "https://my-extra-index-url.com"
```

!!! note

    These settings, like other UV settings, can be set with the `UV_*` environment variables: `UV_INDEX_URL` and `UV_EXTRA_INDEX_URL`. One can also provide [context variables](context.md).

### Inheritance

UV virtual environments can be inherited by other spaces, for example:

```toml
[spaces.default]
venv = "requirements.txt"

[spaces.lint]
venv = {type = "space", name = "default"}
```

!!! remember

    You can also set the default virtualenv for every space with `[defaults.venv]`.

## Virtual Environment Storage

Virtual environments are stored in `._qik/venv` of the project. They cannot be cached in a qik cache at the moment.

## Additional Configuration

UV can be configured by setting the `UV_*` environment variables. See [the UV docs](https://docs.astral.sh/uv/configuration/environment/).