from typing import TYPE_CHECKING
import pathlib

import msgspec

import qik.cache
import qik.conf2
import qik.ctx
import qik.func
import qik.s3

if TYPE_CHECKING:
    from qik.runnable import Runnable


class S3PluginCache(qik.conf2.BaseCache, frozen=True, tag="s3p"):
    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None


class S3(msgspec.Struct, qik.cache.Local, frozen=True, dict=True):
    """A custom cache using the S3 backend"""

    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None

    def remote_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return pathlib.Path(self.prefix) / f"{runnable.slug}-{hash}"

    @qik.func.cached_property
    def client(self) -> qik.s3.Client:
        return qik.s3.Client(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
        )

    def on_miss(self, *, runnable: Runnable, hash: str) -> None:
        super().pre_get(runnable=runnable, hash=hash)

        self.client.download_dir(
            bucket_name=self.bucket,
            prefix=self.remote_path(runnable=runnable, hash=hash),
            dir=self.base_path(runnable=runnable, hash=hash),
        )

    def post_set(self, *, runnable: Runnable, hash: str, manifest: qik.cache.Manifest) -> None:
        super().post_set(runnable=runnable, hash=hash, manifest=manifest)

        self.client.upload_dir(
            bucket_name=self.bucket,
            prefix=self.remote_path(runnable=runnable, hash=hash),
            dir=self.base_path(runnable=runnable, hash=hash),
        )


def factory(name: str, conf: S3PluginCache) -> S3:
    endpoint_url = qik.ctx.format(conf.endpoint_url)
    endpoint_url = None if endpoint_url == "None" else endpoint_url
    return S3(
        bucket=qik.ctx.format(conf.bucket),
        prefix=qik.ctx.format(conf.prefix),
        aws_access_key_id=qik.ctx.format(conf.aws_access_key_id),
        aws_secret_access_key=qik.ctx.format(conf.aws_secret_access_key),
        aws_session_token=qik.ctx.format(conf.aws_session_token),
        region_name=qik.ctx.format(conf.region_name),
        endpoint_url=endpoint_url,
    )


qik.conf2.register_cache_type(S3PluginCache, "qik.s3p.qikplugin.factory")
