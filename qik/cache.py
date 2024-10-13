from __future__ import annotations

import base64
import pathlib
import pkgutil
import threading
from typing import TYPE_CHECKING, Iterator

import msgspec

import qik.conf
import qik.ctx
import qik.errors
import qik.file
import qik.func
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
        return self.base_path(runnable=runnable, hash=hash) / f"{runnable.slug}.json"

    def log_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return self.base_path(runnable=runnable, hash=hash) / f"{runnable.slug}.out"

    def pre_get(self, *, runnable: Runnable, hash: str) -> None:
        pass

    def post_set(self, *, runnable: Runnable, hash: str, manifest: Manifest) -> None:
        pass

    def on_miss(self, *, runnable: Runnable, hash: str) -> None:
        raise NotImplementedError

    def restore_artifacts(self, *, runnable: Runnable, hash: str, artifacts: list[str]) -> None:
        pass

    def import_artifacts(self, *, runnable: Runnable, hash: str) -> list[str]:
        return []

    def get(self, runnable: Runnable, artifacts: bool = True) -> Entry | None:
        hash = runnable.hash()
        self.pre_get(runnable=runnable, hash=hash)

        base_path = self.base_path(runnable=runnable, hash=hash)
        manifest_path = self.manifest_path(runnable=runnable, hash=hash)

        def _get_entry() -> Entry:
            manifest = msgspec.json.decode(manifest_path.read_bytes(), type=Manifest)
            if manifest.hash != hash:
                raise FileNotFoundError("Manifest not found.")

            log = pathlib.Path(base_path / manifest.log).read_text() if manifest.log else None
            if artifacts:
                self.restore_artifacts(runnable=runnable, hash=hash, artifacts=manifest.artifacts)
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

        artifacts = self.import_artifacts(runnable=runnable, hash=result.hash)
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

    def get(self, runnable: Runnable, artifacts: bool = True) -> Entry | None:
        pass

    def set(self, runnable: Runnable, result: Result) -> None:
        pass


@qik.func.cache
def _install_custom_merge_driver():
    """Install qik's custom git merge driver."""
    script_path = pathlib.Path(__file__).parent / "merge.sh"
    custom_merge_driver_install = f'git config merge.qik.driver "sh {script_path} %O %A %B"'
    qik.shell.exec(custom_merge_driver_install)


@qik.func.cache
def _add_cache_dir_to_git_attributes():
    """Add .qik to .gitattributes so that it appears differently in diff.

    https://docs.github.com/en/repositories/working-with-files/managing-files/customizing-how-changed-files-appear-on-github
    """
    git_root_dir = pathlib.Path(
        qik.shell.exec("git rev-parse --absolute-git-dir").stdout.strip()
    ).parent
    attrs_path = git_root_dir / ".gitattributes"
    ignore_glob = qik.conf.root().relative_to(git_root_dir) / ".qik/**/*"
    attrs_line = f"{ignore_glob} linguist-generated=true merge=qik\n"
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

    def post_set(self, *, runnable: Runnable, hash: str, manifest: Manifest) -> None:
        git_add = [str(self.manifest_path(runnable=runnable, hash=hash))]

        if manifest.log:
            git_add.append(str(self.log_path(runnable=runnable, hash=hash)))

        if runnable.artifacts:
            git_add.extend(runnable.artifacts)

        git_add_files = " ".join(git_add)
        with _LOCK:
            qik.shell.exec(f"git add -N {git_add_files}")
            _add_cache_dir_to_git_attributes()
            _install_custom_merge_driver()


class Local(Cache):
    """A local cache in the ._qik directory."""

    def base_path(self, *, runnable: Runnable, hash: str) -> pathlib.Path:
        return qik.conf.priv_work_dir() / "cache" / runnable.cmd

    def restore_artifacts(self, *, runnable: Runnable, hash: str, artifacts: list[str]) -> None:
        base_path = self.base_path(runnable=runnable, hash=hash)
        for artifact in set(artifacts):
            name = _artifact_name(artifact)
            qik.file.copy(str(base_path / name), artifact)

    def import_artifacts(self, *, runnable: Runnable, hash: str) -> list[str]:
        base_path = self.base_path(runnable=runnable, hash=hash)
        artifacts = [str(path) for path in _walk_artifacts(runnable)]
        for artifact in artifacts:
            name = _artifact_name(artifact)
            qik.file.copy(artifact, str(base_path / name))

        return artifacts


@qik.func.cache
def load(name: str) -> Cache:
    proj = qik.conf.project()

    match name:
        case "repo":
            return Repo()
        case "local":
            return Local()
        case "none":
            return Uncached()
        case custom:
            if conf := proj.caches.get(custom):
                factory = qik.conf.get_type_factory(conf)
                return pkgutil.resolve_name(factory)(name, conf)
            else:
                raise qik.errors.UnconfiguredCache(f'Unconfigured cache - "{custom}"')
