# Command Examples

Below are common command definitions. Note that we only provide basic dependencies in the examples. Some examples that depend on the Python import graph assume the [Pygraph plugin](plugin_pygraph.md) is installed.

## Linting, Formatting, and Type Checking

### Pyright Type Checking

```toml
[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
cache = "repo"
```

### Black Formatting

```toml
[commands.format]
exec = "black {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

### Flake8 Linting

```toml
[commands.lint]
exec = "flake8 {module.dir}"
deps = ["{module.dir}/**.py"]
cache = "repo"
```

### Ruff Formatting and Linting

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

## Locking Environments

### Pip Tools

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
```

### Poetry

```toml
[commands.lock]
exec = "poetry lock"
deps = ["pyproject.toml"]
artifacts = ["poetry.lock"]
```

## Building Documentation

### MkDocs

```toml
[commands.build-docs]
exec = "mkdocs build"
deps = ["docs/**", "mkdocs.yml"]
artifacts = ["site/**"]
```

### Sphinx

```toml
[commands.build-docs]
exec = "cd docs && make html"
deps = ["docs/**"]
artifacts = ["docs/build/**"]
```

## Unit Tests

### Pytest

```toml
[commands.test]
exec = "pytest {module.dir}"
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
```

### Pytest with Coverage

```toml
[commands.test]
exec = "pytest {module.dir} --cov-report xml:{module.name}-coverage.xml"
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
artifacts = ["{module.name}-coverage.xml"]
```

### Pytest with Django

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
deps = [{type = "pygraph", pyimport = "{module.pyimport}"}]
```

## Generating API Clients

### Orval

```toml
[commands.generate-api-client]
exec = "python manage.py generate_openapi_spec > openapi.json && npm run orval"
deps = ["backend/**/api/**.py"]
cache = "repo"
```

## Database Schemas

### Cache Migrated Django Postgres Database

```toml
[commands.migrate-db]
exec = "python manage.py migrate && pg_dump db_name > dump.sql"
deps = ["requirements.txt", "**/migrations/**.py"]
cache = "repo"
```
