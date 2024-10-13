# Caching

Here we go over how qik caches command results, when to use different cache types, and how to configure caching behavior.

## How it Works

Qik uses [git](https://git-scm.com) as the underlying hashing engine. In other words, qik does not rely on file modification time stamps and instead uses the hash of the file contents.

For example, say we have the following command:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
```

Qik uses a combination of `git ls-files` and `git hash-object` to retrieve the hash of `deps`. If the dependencies or command definition change, the hash changes.

!!! remember

    Files not in the git index are not included in the hash.

Other dependency types, such as [pygraph imports](plugin_pygraph.md) are still tied to underlying files. For example, qik's pygraph plugin stores a set of globs for every module import, allowing you to cache this locally, remotely, or in your repo to interactive run commands based on import graph changes.

!!! note

    This same concept applies to other dependencies like distributions and virtual environments. For example, virtualenv plugins like [UV](plugin_uv.md) ensure commands are cached based off the virtualenv lock file.

## Configuration

The cache can be configured on a per-command basis with the `cache` option:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache = "repo"
```

The cache defaults to the `local` cache. Commands without `deps` are never cached, even if there are `base` dependencies configured.

When a command is cached, the exit code and log are stored so that the command can be replayed. Remote caches will store artifacts, ensuring they are properly restored when cached commands are replayed.

By default, only commands with a successful exit code of 0 are cached. This behavior can be overridden with the `cache_when` option on a command:

```toml
[commands.lock]
exec = "pip-compile > requirements.txt"
deps = ["requirements.in"]
cache-when = "always"
```

Override the default behavior globally for every command with `[defaults.cache_when]`:

```toml
[defaults]
cache-when = "always"
```

## Cache Types

Qik offers three primary cache types. The `local` and `repo` caches are provided by qik for maintaining a cache local to your machine or to your project. Remote caches are provided by plugins like [S3](plugin_s3.md) for creating a global shared cache outside of your repo.

We dive into all three cache types here.

### The Local Cache

By default, all commands use the `local` cache. In other words, command hashes and stdout will be cached in the local `._qik/cache` folder. Only the most recent results are cached.

To clear the local cache, delete the `._qik/cache` folder.

!!! note

    The `._qik` folder is a private working directory with other caches, including import graph data, virtualenvs, etc. It's safe to delete the entire folder.

<a id="repo"></a>

### The Repo Cache

The `repo` cache stores the most recent result in `.qik/cache`. It's useful for architecture-agnostic commands, for example, generating lock files, linting, type checking, code formatting, and auto-generating API clients. The [Pygraph plugin](plugin_pygraph.md) can be configured to cache the graph in the repository as well.

Cache files are automatically added to the git index with `git add -N`. The `.gitattributes` file is also updated to ensure `.qik` files are ignored in Github diffs. [See these docs](https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github) for more information.

Updates to the repo cache can be a source git merge conflicts. Qik automatically installs a custom merge strategy in `.gitattributes` and the local git config to ensure that your cache changes always take precedence over remote branches.

!!! warning

    Keep in mind that providers like Github cannot use these strategies, so rebases and automatic merge conflicts must still be resolved locally.

<a id="remote"></a>

## Remote Caches

Remote caches store all runs in a remote shared cache. They use the `local` cache as hot storage.

Qik currently supports [AWS S3](https://aws.amazon.com/s3/) as a remote cache plugin. See [the S3 plugin docs](plugin_s3.md) for how to enable and configure S3 caching, which is the preferred mechanism for [enhancing CI/CD times with qik](cookbook_cicd.md).
