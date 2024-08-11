# Cookbook

Common command definitions, runner examples, and other snippets.

## Runner Examples

Some useful examples of using the runner.

!!! remember

    CLI arguments do not override direct command configuration. For example, a command with `cache: repo` will not have the cache overridden when using `--cache`.

### Watch Repo-Cached Commands

```bash
qik --cache-type repo --watch
```

### Run All Commands Serially

```bash
qik -n 1
```

### Check for Warm Cache for Specific Commands

```bash
qik command_one command_two --cache-status warm --ls
```

### Fail if Commands have Cold Cache

```bash
qik --cache-status cold --ls --fail
```

### Run Commands Since `main` Branch

```bash
qik --since main
```

### Show Output of Successful and Failed Commands

```bash
qik -v 2
```

### Cache All Finished Commands

```bash
qik --cache-when finished
```

### Set the Default Cache

```bash
qik --cache remote_cache_name
```

## Command Examples

### Linting, Formatting, and Type Checking

!!! note

    In all these examples, we're using the `repo` cache. We don't recommend a remote cache with formatters or any tool that edits code, otherwise the `artifacts` of these commands would need to be `**.py`, which would upload all Python files to the cache on every cold run.

#### Pyright Type Checking

```toml
[commands.check_types]
exec = "pyright {module.dir}"
deps = [
    {type = "module", name = "{module.name}"},
    {type = "dist", name = "pyright"}
]
cache = "repo"
```

#### Black Formatting

```toml
[commands.format]
exec = "black {module.dir}"
deps = ["{module.dir}/**.py", {type = "dist", name = "black"}]
cache = "repo"
```

#### Flake8 Linting

```toml
[commands.lint]
exec = "flake8 {module.dir}"
deps = ["{module.dir}/**.py", {type = "dist", name = "flake8"}]
cache = "repo"
```

#### Ruff Formatting and Linting

```toml
[commands.format]
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py", {type = "dist", name = "ruff"}]
cache = "repo"

[commands.lint]
exec = "ruff check {module.dir}"
deps = [
    "{module.dir}/**.py",
    {type = "dist", name = "ruff"}
    {type = "command", name = "format"},
]
```

### Locking Environments

!!! note

    In all these examples, we're not specifying a cache. We specify the generated `artifacts` in case a remote cache is used.

#### Pip Tools

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
artifacts = "requirements.txt"
deps = ["requirements.in", {type = "dist", name = "pip-tools"}]
```

#### Poetry

```toml
[commands.lock]
exec = "poetry lock"
artifacts = "poetry.lock"
deps = ["pyproject.toml", {type = "dist", name = "poetry"}]
```


