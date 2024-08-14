---
date:
  created: 2024-08-12
authors:
  - wes
---

# Why I'm Building Qik

I'm a fan of monorepos. I like to avoid overly complex infrastructure. However, the consequences can oftentimes be painfully slow CI and a poor developer experience.

For example, huge Django projects can have seconds of latency to run a command, not to mention minutes of running migrations in CI *just to start your test suite*. Oh, you have a failing test? Have fun *literally re-running everything from scratch on the next commit*.

Although tools like [nx](https://nx.dev) have greatly benefitted JavaScript monorepos, I desired a tool like [make](https://www.gnu.org/software/make/) for large Python projects that could:

- Understand the import graph, running only the things that matter.
- Support multiple virtual environments and enforce import boundaries.
- Use full file hashing to understand what's changed vs. file modification times.

Enter qik (*quick*).

<!-- more -->

## A Modern Command Runner

Qik revolves around command definitions in `qik.toml`. Although qik has special functionality for Python repos, any project can use it as a command runner. For example, here's a command to lock a requirements file using [pip-tools](https://github.com/jazzband/pip-tools):

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
```

Once [installed](../../guide.md#installation), run `qik lock` to compile your lock file.

### Caching

Where qik shines is its ability to cache command results. Here we're caching a lock file in our repository when `requirements.in` changes:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Running `qik lock` will replay the command if nothing has changed. Want to use a shared remote S3 cache instead? Configure it and specify the `artifacts` of the command:

```toml
[caches.remote]
type = "s3"
bucket = "my-cache-bucket"

[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
artifacts = ["requirements.txt"]
cache = "remote"
```

When the cache is warm, qik will replay the command output, extract the `requirements.txt` file, and exit with the cached exit code.

### Advanced Dependencies

Qik dependencies can be glob patterns and other advanced types. For example, let's make sure we break the cache whenever the [PyPI distribution of pip-tools](https://pypi.org/project/pip-tools/) is different:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in", {type = "dist", name = "pip-tools"}]
```

Furthermore, let's break the cache when executed on a different machine architecture using [qik context](../../context.md):

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = [
    "requirements.in",
    {type = "dist", name = "pip-tools"},
    {type = "const", val = "{ctx.qik.arch}"
]
```

### Parametrizing Modules

Define modules for your project and parametrize commands over them:

```toml
modules = ["my.module.a", "my.module.b"]

[commands.lint]
exec = "ruff check {module.dir}"
deps = ["{module.dir}/**.py"]
```

Qik runs commands in parallel by default. Use `-m` to specify individual modules.

### Depending on the Import Graph

Commands such as type checkers or test runners need to re-run when the import graph changes:

```toml
modules = ["my.module.a", "my.module.b"]

[commands.check-types]
exec = "pyright {module.dir}"
deps = [{type = "module", name = "{module.name}"}]
cache = "repo"
```

If `my.module.b` imports `my.module.a`, changes to files in `my.module.a` will cause both module-level invocations to re-run. The `module` dependency type also dynamically adds `dist` dependencies for imported external packages.

### Watching for Changes

There is no need to run individual watchers for every command. Watch all commands:

```bash
qik --watch
```

Or select commands for watching:

```bash
qik command_one command_two --watch
```

## CI/CD Optimization

Qik's command selection and remote caching can help optimize your CI/CD flow:

- Use the `--cache-status` selector to immediately run warm commands and dynamically schedule the rest (if your CI provider allows it, like [CircleCI dynamic configs](https://circleci.com/docs/dynamic-config/))
- Use a [remote cache like S3](../../caching.md#s3) with your existing CI config to replay commands that haven't changed, for example, extracting coverage artifacts from a test run
- Use a [repo cache](../../caching.md#repo) to store command hashes and artifacts directly in the repo, such as lock files, type checking and linting results, auto-generated or formatted code, etc. Qik replaces the need to write custom CI checks to ensure auto-generated files are up to date.

There's a [CI/CD guide in the docs](../../ci.md) for more tips and tricks.

## Spaces, Virtual Envs, and Import Boundaries

Qik's ultimate goal is to help architect large monorepos. Qik *spaces*, an upcoming feature, will support multiple virtual environments (e.g., [uv](https://github.com/astral-sh/uv), [pip-tools](https://github.com/jazzband/pip-tools), [poetry](https://python-poetry.org)) and enable import boundaries in your monorepo. I'm also planning for direct support with [conda](https://conda.io) to enable environments with different Python or Node versions.

See the [roadmap](../../roadmap.md) for a full picture of where qik is headed.

## Finally

I am very bullish on Python's future, especially with the [Rust](https://www.rust-lang.org)-ification and performance optimizations in so many tools. We just need better ways to avoid the downsides of the sprawl associated with huge Python projects. Is qik the answer? That is TBD, but I felt compelled to share my approach of first focusing on an extensible and advanced command runner.

Qik is very much in its infancy. Here's how you can get involved:

- [Star or follow the project on Github](https://github.com/Opus10/qik) to see updates.
- [Open a discussion](https://github.com/Opus10/qik/discussions) if you have any ideas for improvement.
- [Open an issue](https://github.com/Opus10/qik/issues) if you're using it and are having trouble.
- [Contact me privately](mailto:wesleykendall@gmail.com) for anything else.
