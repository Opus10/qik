import concurrent.futures
import functools
import os
import pathlib
from typing import TYPE_CHECKING

import msgspec

import qik.file

if TYPE_CHECKING:
    import boto3
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

    @functools.cached_property
    def s3_session(self) -> boto3.Session:
        return boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
        ).resource("s3")

    def download_dir(
        self, *, bucket_name: str, prefix: pathlib.Path, dir: pathlib.Path, max_workers: int = 10
    ) -> None:
        bucket = self.s3_session.Bucket(bucket_name)

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
        bucket = self.s3_session.Bucket(bucket_name)

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
