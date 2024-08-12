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

Below are common command definitions. Note that we only provide basic dependencies in the examples. We also recommend to:

- Depend on your requirements file or the tool's PyPI distribution. See [depending on distributions](commands.md#distributions).
- Create a [global dependency](commands.md#global) on the Python version.

### Linting, Formatting, and Type Checking

#### Pyright Type Checking

```toml
[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

#### Black Formatting

```toml
[commands.format]
exec = "black {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

#### Flake8 Linting

```toml
[commands.lint]
exec = "flake8 {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

#### Ruff Formatting and Linting

```toml
[commands.format]
exec = "ruff format {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"

[commands.lint]
exec = "ruff check {module.dir}"
deps = [
    "{module.dir}/**.py",
    {type = "command", name = "format"},
]
```

### Locking Environments

#### Pip Tools

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
```

#### Poetry

```toml
[commands.lock]
exec = "poetry lock"
deps = ["pyproject.toml"]
artifacts = ["poetry.lock"]
```

### Building Documentation

#### MkDocs

```toml
[commands.build-docs]
exec = "mkdocs build"
deps = ["docs/**", "mkdocs.yml"]
artifacts = ["site/**"]
```

#### Sphinx

```toml
[commands.build-docs]
exec = "cd docs && make html"
deps = ["docs/**"]
artifacts = ["docs/build/**"]
```

### Unit Tests

#### Pytest

```toml
[commands.test]
exec = "pytest {module.dir}"
deps = [{type = "module", name = "{module.name}"}]
```

#### Pytest with Coverage

```toml
[commands.test]
exec = "pytest {module.dir} --cov-report xml:{module.name}-coverage.xml"
deps = [{type = "module", name = "{module.name}"}]
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
deps = [{type = "module", name = "{module.name}"}]
```

### Generating API Clients

#### Orval

```toml
[commands.generate-api-client]
exec = "python manage.py generate_openapi_spec > openapi.json && npm run orval"
deps = ["backend/**/api/**.py"]
cache = "repo"
```

### Database Schemas

#### Cache Migrated Django Postgres Database

```toml
[commands.migrate-db]
exec = "python manage.py migrate && pg_dump db_name > dump.sql"
deps = ["requirements.txt", "**/migrations/**.py"]
cache = "repo"
```
