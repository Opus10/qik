# S3

The S3 plugin allows [AWS S3](https://aws.amazon.com/s3/) to be used as a remote cache for qik.

## Installation

The S3 plugin requires additional dependencies. `pip install "qik[s3]"` to install them.

!!! note

    One can manually install `boto3` too.

After this, configure the plugin in `qik.toml`:

```toml
[plugins]
s3 = "qik.s3"
```

## Configuration

After installation, define a custom cache in `qik.toml`:

```toml
[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
```

Ensure that you either have [AWS environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) or an [AWS config file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-a-configuration-file).

You can also supply authentication information via [context](context.md):

```toml
ctx = ["aws_access_key_id", "aws_secret_access_key"]

[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
aws-access-key-id = "{ctx.project.aws_access_key_id}"
aws-secret-access-key = "{ctx.project.aws_secret_access_key}"
```

You can also configure `region-name` and `aws-session-token`.

## Usage

When using an S3 cache, all command results and artifacts are stored. We recommend configuring a [lifecycle policy](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) on your bucket to delete old entries.

Whenever cached entries are found, they're downloaded to the local cache at `._qik/cache` first. This local cache serves as a hot cache if the commands are executed again.
