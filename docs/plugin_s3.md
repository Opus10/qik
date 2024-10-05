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

If the default AWS environment variables are used by another service, you can supply authentication information via [context](context.md):

```toml
vars = ["aws_access_key_id", "aws_secret_access_key"]

[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
aws-access-key-id = "{ctx.project.aws_access_key_id}"
aws-secret-access-key = "{ctx.project.aws_secret_access_key}"
```

You can also configure `region-name` and `aws-session-token`.
