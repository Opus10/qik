from __future__ import annotations

import concurrent.futures
import os
import pathlib
from typing import TYPE_CHECKING

import boto3.s3
import msgspec

import qik.cache
import qik.ctx
import qik.file
import qik.func

if TYPE_CHECKING:
    import boto3
    from boto3.resources.base import ServiceResource

    from qik.runnable import Runnable
    from qik.s3.qikplugin import S3Conf
else:
    import qik.lazy

    boto3 = qik.lazy.module("boto3")


def _download_file(*, bucket, obj, dir: pathlib.Path, prefix: pathlib.Path):
    target = dir / os.path.relpath(obj.key, str(prefix))

    if obj.key[-1] == "/":
        return  # Skip directories

    try:
        bucket.download_file(obj.key, target)
    except FileNotFoundError:
        qik.file.make_parent_dirs(target)
        bucket.download_file(obj.key, target)

    return obj.key


def _upload_file(*, bucket, prefix: pathlib.Path, path: pathlib.Path, dir: pathlib.Path) -> str:
    relative_path = os.path.relpath(path, dir)
    s3_key = str((prefix / relative_path)).replace("\\", "/")
    bucket.upload_file(path, s3_key)
    return s3_key


class Client(msgspec.Struct, frozen=True, dict=True):
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None

    @qik.func.cached_property
    def s3_session(self) -> ServiceResource:
        s3_kwargs = {"endpoint_url": self.endpoint_url} if self.endpoint_url else {}
        return boto3.Session(  # type: ignore
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
        ).resource("s3", **s3_kwargs)  # type: ignore

    def download_dir(
        self, *, bucket_name: str, prefix: pathlib.Path, dir: pathlib.Path, max_workers: int = 10
    ) -> None:
        bucket = self.s3_session.Bucket(bucket_name)  # type: ignore

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_download_file, bucket=bucket, obj=obj, dir=dir, prefix=prefix)
                for obj in bucket.objects.filter(Prefix=str(prefix))
            ]

            for future in concurrent.futures.as_completed(futures):
                # TODO: Better handle partial upload failures
                future.result()

    def upload_dir(
        self, *, bucket_name: str, prefix: pathlib.Path, dir: pathlib.Path, max_workers: int = 10
    ) -> None:
        bucket = self.s3_session.Bucket(bucket_name)  # type: ignore

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _upload_file,
                    prefix=prefix,
                    bucket=bucket,
                    path=pathlib.Path(root) / file,
                    dir=dir,
                )
                for root, _, files in os.walk(dir)
                for file in files
            ]

            for future in concurrent.futures.as_completed(futures):
                # TODO: Better handle partial upload failures
                future.result()


class S3Cache(msgspec.Struct, qik.cache.Local, frozen=True, dict=True):
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
    def client(self) -> Client:
        return Client(
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


def factory(name: str, conf: S3Conf) -> S3Cache:
    endpoint_url = qik.ctx.format(conf.endpoint_url)
    endpoint_url = None if endpoint_url == "None" else endpoint_url
    return S3Cache(
        bucket=qik.ctx.format(conf.bucket),
        prefix=qik.ctx.format(conf.prefix),
        aws_access_key_id=qik.ctx.format(conf.aws_access_key_id),
        aws_secret_access_key=qik.ctx.format(conf.aws_secret_access_key),
        aws_session_token=qik.ctx.format(conf.aws_session_token),
        region_name=qik.ctx.format(conf.region_name),
        endpoint_url=endpoint_url,
    )
