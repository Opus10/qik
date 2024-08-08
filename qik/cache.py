from __future__ import annotations

import base64
import functools
import pathlib
import threading
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.ctx
import qik.file
import qik.s3
import qik.shell

if TYPE_CHECKING:
    from qik.runnable import Result, Runnable


# A global lock for git index manipulation operations
_LOCK = threading.Lock()


class Manifest(msgspec.Struct, frozen=True, omit_defaults=True):
    name: str
    hash: str
    code: int
    log: str | None = None
    artifacts: list[str] = []


class Entry(msgspec.Struct, frozen=True):
    manifest: Manifest
    log: str | None = None


def _walk_artifacts(runnable: Runnable) -> Iterator[pathlib.Path]:
    """Walk artifact globs of a runnable."""
    for artifact in set(runnable.artifacts):
        yield from qik.conf.root().glob(artifact)


def _artifact_name(path: str | pathlib.Path) -> str:
    return f"artifact-{base64.urlsafe_b64encode(str(path).encode()).decode()}"


class Cache:
    @property
    def type(self) -> str:
        return self.__class__.__name__.lower()

    def base_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        raise NotImplementedError

    def manifest_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return self.base_path(runnable=runnable, hash=hash) / f"{runnable.name}.json"

    def log_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return self.base_path(runnable=runnable, hash=hash) / f"{runnable.name}.out"

    def pre_get(self, *, runnable: Runnable, hash: str) -> None:
        pass

    def post_set(self, *, runnable: Runnable, hash: str, manifest: Manifest) -> None:
        pass

    def on_miss(self, *, runnable: Runnable, hash: str) -> None:
        raise NotImplementedError

    def get_artifacts(self, *, runnable: Runnable, hash: str, artifacts: list[str]) -> None:
        pass

    def set_artifacts(self, *, runnable: Runnable, hash: str) -> list[str]:
        return []

    def get(self, runnable: Runnable) -> Entry | None:
        hash = runnable.hash()
        self.pre_get(runnable=runnable, hash=hash)

        base_path = self.base_path(runnable=runnable, hash=hash)
        manifest_path = self.manifest_path(runnable=runnable, hash=hash)

        def _get_entry() -> Entry:
            manifest = msgspec.json.decode(manifest_path.read_bytes(), type=Manifest)
            if manifest.hash != hash:
                raise FileNotFoundError("Manifest not found.")

            log = pathlib.Path(base_path / manifest.log).read_text() if manifest.log else None
            self.get_artifacts(runnable=runnable, hash=hash, artifacts=manifest.artifacts)
            return Entry(manifest=manifest, log=log)

        try:
            return _get_entry()
        except FileNotFoundError:
            try:
                self.on_miss(runnable=runnable, hash=hash)
            except NotImplementedError:
                return None

        try:
            return _get_entry()
        except FileNotFoundError:
            return None

    def set(self, runnable: Runnable, result: Result) -> None:
        manifest_path = self.manifest_path(runnable=runnable, hash=result.hash)
        log_path = self.log_path(runnable=runnable, hash=result.hash)

        artifacts = self.set_artifacts(runnable=runnable, hash=result.hash)
        manifest = Manifest(
            name=runnable.name,
            code=result.code,
            hash=result.hash,
            log=log_path.name if result.log else None,
            artifacts=artifacts,
        )
        qik.file.write(manifest_path, msgspec.json.encode(manifest))
        if result.log:
            qik.file.write(log_path, result.log)

        self.post_set(runnable=runnable, hash=result.hash, manifest=manifest)


class Uncached(Cache):
    @property
    def type(self) -> str:
        return "none"

    def get(self, runnable: Runnable) -> Entry | None:
        pass

    def set(self, runnable: Runnable, result: Result) -> None:
        pass


@functools.cache
def _add_cache_dir_to_git_attributes():
    """Add .qik to .gitattributes so that it appears differently in diff.

    https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github
    """
    git_root_dir = pathlib.Path(qik.shell.exec("git rev-parse --git-dir").stdout.strip()).parent
    attrs_path = git_root_dir / ".gitattributes"
    ignore_glob = qik.conf.root().relative_to(git_root_dir) / ".qik/**/*"
    attrs_line = f"{ignore_glob} linguist-generated=true\n"
    try:
        gitattributes = attrs_path.read_text()
        if attrs_line not in gitattributes:
            attrs_path.write_text(f"{attrs_line}{gitattributes}")
    except FileNotFoundError:
        attrs_path.write_text(attrs_line)
        qik.shell.exec(f"git add -N {attrs_path}")


class Repo(Cache):
    """A cache in the local git repository."""

    def base_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return qik.conf.pub_work_dir() / "cache" / runnable.cmd

    def post_set(self, *, runnable: Runnable, hash: str, manifest: Manifest) -> list[str]:
        git_add = [str(self.manifest_path(runnable=runnable, hash=hash))]

        if manifest.log:
            git_add.append(str(self.log_path(runnable=runnable, hash=hash)))

        if runnable.artifacts:
            git_add.extend(runnable.artifacts)

        git_add_files = " ".join(git_add)
        with _LOCK:
            qik.shell.exec(f"git add -N {git_add_files}")
            _add_cache_dir_to_git_attributes()


class Local(Cache):
    """A local cache in the .qik directory."""

    def base_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return qik.conf.priv_work_dir() / "cache" / f"{runnable.name}-{hash}"

    def get_artifacts(self, *, runnable: Runnable, hash: str, artifacts: list[str]) -> None:
        base_path = self.base_path(runnable=runnable, hash=hash)
        for artifact in set(artifacts):
            name = _artifact_name(artifact)
            qik.file.copy(str(base_path / name), artifact)

    def set_artifacts(self, *, runnable: Runnable, hash: str) -> list[str]:
        base_path = self.base_path(runnable=runnable, hash=hash)
        artifacts = [str(path) for path in _walk_artifacts(runnable)]
        for artifact in artifacts:
            name = _artifact_name(artifact)
            qik.file.copy(artifact, str(base_path / name))

        return artifacts


class S3(msgspec.Struct, Local, frozen=True, dict=True):
    """A custom cache using the S3 backend"""

    bucket: str
    prefix: str = ""
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None

    @functools.cached_property
    def client(self) -> qik.s3.Client:
        return qik.s3.Client(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
        )

    def on_miss(self, runnable: Runnable, hash: str) -> None:
        super().pre_get(runnable=runnable, hash=hash)
        base_path = self.base_path(runnable=runnable, hash=hash)
        self.client.download_dir(
            bucket_name=self.bucket,
            prefix=pathlib.Path(self.prefix) / base_path.name,
            dir=base_path,
        )

    def post_set(self, runnable: Runnable, hash: str, manifest: Manifest) -> None:
        super().post_set(runnable=runnable, hash=hash, manifest=manifest)
        base_path = self.base_path(runnable=runnable, hash=hash)
        self.client.upload_dir(
            bucket_name=self.bucket,
            prefix=pathlib.Path(self.prefix) / base_path.name,
            dir=base_path,
        )


def factory(conf: qik.conf.Cache) -> Cache:
    match conf:
        case qik.conf.S3Cache():
            return S3(
                bucket=qik.ctx.format(conf.bucket),
                prefix=qik.ctx.format(conf.prefix),
                aws_access_key_id=qik.ctx.format(conf.aws_access_key_id),
                aws_secret_access_key=qik.ctx.format(conf.aws_secret_access_key),
                aws_session_token=qik.ctx.format(conf.aws_session_token),
                region_name=qik.ctx.format(conf.region_name),
            )
        case other:
            raise ValueError(f'Invalid cache backend - "{other}".')


@functools.cache
def load(backend: str | None) -> Cache:
    proj = qik.conf.project()

    match backend:
        case "repo":
            return Repo()
        case "local":
            return Local()
        case "none" | None:
            return Uncached()
        case custom:
            if conf := proj.caches.get(custom):
                return factory(conf)
            else:
                raise ValueError(f'Unconfigured cache - "{custom}"')
