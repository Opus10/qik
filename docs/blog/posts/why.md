---
date:
  created: 2024-08-12
authors:
  - wes
---

# Why I Built Qik

I'm a fan of monorepos. I like to avoid overly complex infrastructure. Oftentimes the consequences of monorepos are painfully slow CI and a hodgepodge of developer commands.

I continually wonder why it's so difficult to *just run the things that matter* in CI. Is this the best we can do, paying to continually re-run things?

Although tools like [nx](https://nx.dev) have helped this experience in JavaScript monorepos, I desired an experience similar to [make](https://www.gnu.org/software/make/) that could understand the import graph of Python projects and performantly use file hashes to understand what has changed.

I wanted a fully open source tool that could be used with any CI service and caching backend. Enter qik.

<!-- more -->

## A Modern Command Runner

Qik revolves around command definitions in `qik.toml`. Although qik has special functionality for Python repos, any project can use it as a command runner. For example, here's a command to lock a requirements file using [pip-tools](https://github.com/jazzband/pip-tools):

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
```

Once [installed](../../guide.md#installation), run `qik lock` to compile your lock file.

### Caching

Where qik shines is its ability to cache commands results. Here we're caching the results in our repository when `requirements.in` changes:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

Running `qik lock` will now cache the latest command results in your repository. Want to use a shared remote S3 cache instead? Configure it and specify the `artifacts` of the command:

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

When the cache is warm, qik will immediately show the command output, extract the cached `requirements.txt` file, and exit with the cached exit code.

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

The qik command line tool runs in parallel by default. Use `-m` to specify individual modules.

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

We have a [CI/CD guide here](../../ci.md) for tricks on how to optimize continuous integration and delivery. For example, qik's CLI comes with `--cache-type` and `--cache-status` flags to filter commands by the type and status of cache, allowing you to run your warm commands immediately and generate CI config for the cold commands.

Even if your CI provider doesn't allow for dynamic configuration, existing CI configurations can leverage a remote cache to dramatically increase performance for some commands.

## Finally

I am very bullish on Python's future, especially with the [Rust](https://www.rust-lang.org)-ification and performance optimizations in so many tools. However, we need better ways to manage Python repo sprawl and to make development an enjoyable and scalable experience for huge projects.

I'm confident that the right design and community of plugins can enable this. Is qik the answer? That is TBD, but I felt compelled to solve it in the way I hoped it would work.

Qik is in its infancy. Check the [roadmap here](../../roadmap.md) to better understand where I ultimately want to take this, and please [open a discussion](https://github.com/Opus10/qik/discussions) if you have any thoughts!
