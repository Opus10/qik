# Continuous Integration and Delivery

Qik can be used in a number of ways to dramatically increase CI/CD performance. Here we cover various patterns to use with new or existing projects.

!!! tip

    The core `qik` installation is the only requirement needed in CI/CD.

## Ensuring that Repo-Cached Commands are Successful

When using the `repo` cache, we can quickly verify that all commands are successful with:

```bash
qik --cache-type repo --cache-status cold --fail --ls
```

Above, we're doing the following:

- Filtering commands by `--cache-type` of `repo`
- Filtering for any `cold` commands
- Failing if any exist
- Printing the commands that aren't cached

If all commands are cached, we can run them all with:

```bash
qik --cache-type repo
```

The second step ensures that any cached failures are caught. By default, only successful runs are cached, but this may have been overridden with `--cache-when`.

With these commamnds, you now have a fast way to ensure your repo cache is in sync. You also avoid the need to install dependencies of these commands in your CI/CD pipeline.

## Using a Remote Cache

### Basics

If repo-based caching isn't acceptable or you have architecture-specific demands, use a [remote cache](caching.md). Just remember to specify `artifacts` of your commands. For example, let's run [pytest](https://docs.pytest.org/en/stable/) over modules and collect coverage reports:

```toml
[commands.pytest]
exec = "pytest --cov {module.dir} --cov-report xml:{module.name}-coverage.xml"
deps = [{type = "module", name = "{module.imp}"}]
artifacts = ["{module.name}-coverage.xml"]
```

Run `qik pytest --cache my_remote_cache_name`. When the cache is warm, the output will be replayed and the coverage artifacts will be restored.

### Configuration

We recommend making a CI profile to specify the default cache:

```toml
[ctx.ci.qik]
cache = "my_remote_cache_name"
```

Use either `-p ci` or set `QIK__PROFILE=ci` in your environment to use the default CI configuration. If using the [S3 cache](caching.md#s3), remember to set AWS authentication environment variables.

## Isolated Execution

If commands have other [command dependencies](commands.md#command), these will also be selected even if trying to run a single command with `qik <command_name>`. This is normally harmless since these upstream commands are usually cached, however it can be undesirable if the upstream command is using a remote cache.

To bypass this, use `--isolated` when running the command. Remember, using [module dependencies](commands.md#module) will automatically insert dependent commands, so be sure to either validate the repo cache or run upstream commands elsewhere in your CI/CD flow.

## Dynamic CI/CD Config Generation

Some CI/CD services such as [CircleCI](circleci.com) offer the ability to [dynamically generate configuration](https://circleci.com/docs/dynamic-config/). You can leverage this pattern as follows:

- In the initial step, run `qik --cache-status warm` to run all warm commands. All artifacts will be available in your repository to store as CI/CD artifacts.
- Then iterate over `qik --cache-status cold --ls` to configure the remaining jobs for execution.

Keep the following in mind:

- Any commands that have set `cache_when = "finished"` will cache failures, causing the first command to fail.
- Any parametrized commands from `--ls` will be in the format of `{command}@{module}`.

## Running Since a Base Branch

Use `--since <base branch>` to select commands that need to be re-executed since a base branch (e.g. in a pull request). Remember to keep the following in mind:

- If you rely on artifacts such as coverage reports on every CI run, these may not be produced if you don't run those commands.
- Qik is still in beta. It's good to occassionally break the whole cache by [adding a const dependency](commands.md#const) as a [global dependency](commands.md#global).

!!! warning

    We recommend always running every command and leveraging a cache, but using `--since` can help with very large monorepos where this isn't possible.

## Recap

There are several tools at your disposal to optimize your CI/CD experience. By leveraging these, you can:

- Keep your platform-agnostic commands cached in the repo, avoiding the need to ever install these tools or run these commands with your CI/CD provider.
- Use a shared remote cache to avoid re-running the same work.
- Store artifacts of cached runs in the artifact store of your CI/CD provider.
- Dynamically generate CI/CD config by listing commands based on their cache type.

We recommend running `qik --cache-type repo --watch` locally to always keep the repo cache up to date.

Qik is still in beta. Open a [discussion]() if you have other ideas or suggestions on how to improve the local development and CI/CD experience.
