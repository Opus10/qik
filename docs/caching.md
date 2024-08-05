# Caching

Qik is in alpha right now, thus the docs are still being built. We will soon more deeply cover how all caching works and how to configure caching.

## S3

To enable S3 caching, first ensure you have the s3-specific dependencies installed:

```bash
pip install qik[s3]
```

Then define a custom cache in `qik.toml`:

```toml
[caches.my_remote_cache]
type = "s3"
bucket = "my-cache-bucket"
```

Finally, ensure that you either have [AWS environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) or and [AWS config file](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-a-configuration-file).

!!! note

    You can also set `aws-access-key-id` and `aws-secret-access-key` to qik context variables in the cache configuration.