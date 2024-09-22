from __future__ import annotations

import qik.conf


class S3Conf(qik.conf.Cache, frozen=True, tag="s3"):
    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    endpoint_url: str | None = None


qik.conf.register_type(S3Conf, "qik.s3.cache.factory")
