---
hide:
  - navigation
---

# Cookbook

Qik CLI examples, common command definitions, and useful snippets.

## CLI Examples

#### Watch Repo-Cached Commands

```bash
qik --cache-type repo --watch
```

#### Run All Commands Serially

```bash
qik -n 1
```

#### Check for Warm Cache for Specific Commands

```bash
qik command_one command_two --cache-status warm --ls
```

#### Fail if Commands have Cold Cache

```bash
qik --cache-status cold --ls --fail
```

#### Run Commands Since `main` Branch

```bash
qik --since main
```

#### Show Output of Successful and Failed Commands

```bash
qik -v 2
```

#### Cache All Finished Commands

```bash
qik --cache-when finished
```

#### Set the Default Cache

```bash
qik --cache remote_cache_name
```

## Common Command Definitions

### Linting, Formatting, and Type Checking

#### Pyright Type Checking

```toml
[commands.check-types]
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

#### Pip Tools

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in", {type = "dist", name = "pip-tools"}]
artifacts = ["requirements.txt"]
```

#### Poetry

```toml
[commands.lock]
exec = "poetry lock"
deps = ["pyproject.toml", {type = "dist", name = "poetry"}]
artifacts = ["poetry.lock"]
```

### Building Documentation

#### MkDocs

```toml
[commands.build-docs]
exec = "mkdocs build"
deps = ["docs/**", "mkdocs.yml", {type = "dist", name = "mkdocs"}]
artifacts = ["site/**"]
```

#### Sphinx

```toml
[commands.build-docs]
exec = "cd docs && make html"
deps = ["docs/**", {type = "dist", name = "sphinx"}]
artifacts = ["docs/build/**"]
```

### Unit Tests

#### Pytest

```toml
[commands.test]
exec = "pytest {module.dir}"
deps = [
    {type = "module", name = "{module.name}"},
    {type = "dist", name = "pytest"}
]
```

#### Pytest with Coverage

```toml
[commands.test]
exec = "pytest {module.dir} --cov-report xml:{module.name}-coverage.xml"
deps = [
    {type = "module", name = "{module.name}"},
    {type = "dist", name = "pytest"},
    {type = "dist", name = "pytest-cov"}
]
artifacts = ["{module.name}-coverage.xml"]
```

#### Pytest with Django

In `settings.py`:

```python
import os

# Ensure parallel runs name the DB based on the worker
DATABASES = {
    "default": {
        ...,
        "TEST": {
            "NAME": f"test_db_name_{os.environ.get('QIK__WORKER')}"
        }
    }
}
```

```toml
[commands.test]
exec = "pytest {module.dir}"
deps = [
    {type = "module", name = "{module.name}"},
    {type = "dist", name = "pytest"},
    {type = "dist", name = "pytest-django"}
]
```

### Generating API Clients

#### Orval

```toml
[commands.generate-api-client]
exec = "python manage.py generate_openapi_spec > openapi.json && npm run orval"
deps = ["backend/**/api/**.py"]
cache = "repo"
```
