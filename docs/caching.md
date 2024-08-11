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

Other dependency types, such as distributions and modules are still tied to underlying files. For example, qik stores globs for every module import to hash module dependencies. When using `--since` or `--watch` the virtual environment lock file or directory may be used to select commands.

When a command is cached, the exit code and log are stored. Artifacts are also stored when using a remote cache.

## The Repo Cache

The `repo` cache stores the most recent result in `.qik/cache`. It's useful for architecture-agnostic commands, preventing redundant execution in other environments. For example, generating lock files, linting, type checking, code formatting, and auto-generating API clients work well with the `repo` cache. The `qik.graph` plugin stores metadata here too.

Cache files are automatically added to the git index with `git add -N`. The `.gitattributes` file is also updated to ensure `.qik` files are ignored in Github diffs. [See these docs](https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github) for more information.

## The Local Cache

The `local` cache stores the most recent results in the `._qik/cache` folder, which is automatically ignored from the git index.

## Remote Caches

Remote caches store *all* runs remotely. They use the `local` cache as a hot cache for the most recent run. In other words, if you're using a remote cache, you're also first checking the `local` cache.

Qik currently supports [AWS S3](https://aws.amazon.com/s3/) as a remote cache. See the [roadmap](roadmap.md) for our plans to support more caches and support custom cache plugins.

<a id="s3"></a>

## Enabling Remote S3 Caching

First ensure s3-specific dependencies are installed:

```bash
pip install qik[s3]
```

Then define a custom cache in `qik.toml`:

```toml
[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
```

Finally, ensure that you either have [AWS environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) or an [AWS config file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-a-configuration-file).

If the default AWS environment variables are used by another service, you can supply authentication information as [context](context.md):

```toml
vars = ["aws_access_key_id", "aws_secret_access_key"]

[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
aws-access-key-id = "{ctx.project.aws_access_key_id}"
aws-secret-access-key = "{ctx.project.aws_secret_access_key}"
```

You can also configure `region-name` and `aws-session-token`.
