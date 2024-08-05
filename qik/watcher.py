from __future__ import annotations

import fnmatch
import functools
import pathlib
import re
import sys
import threading
from typing import TYPE_CHECKING

import qik.dep
import qik.unset
import qik.venv

if TYPE_CHECKING:
    import watchdog.events as watchdog_events
    import watchdog.observers as watchdog_observers

    from qik.runner import Runner
else:
    import qik.lazy

    watchdog_events = qik.lazy.module("watchdog.events")
    watchdog_observers = qik.lazy.module("watchdog.observers")


@functools.cache
def _parse_dist(path: str) -> None | str:
    match = re.match(r"^(.+)-([^-]+)\.dist-info/RECORD$", path)

    # The pip installation process seems to use "~" as a temporary marker
    # for package names
    if match and not match.group(1).startswith("~"):
        return qik.dep._normalize_dist_name(match.group(1))


def _make_watchdog_handler(*, runner: Runner) -> watchdog_events.FileSystemEventHandler:
    """Create the watchdog event handler.

    Watch for both internal project and virtual env changes.

    Note that we create the class in the function to avoid invoking
    a lazy watchdog import.
    """

    class QikEventHandler(watchdog_events.FileSystemEventHandler):
        def __init__(self):
            self.timer: threading.Timer | None = None
            self.changes: set[qik.dep.BaseDep] = set()
            self.runner = runner
            self.lock = threading.Lock()

        @functools.cached_property
        def qik_file_re(self) -> re.Pattern:
            hidden_files = f"({fnmatch.translate('**/.*')})|({fnmatch.translate('.*')})"
            ignored_patterns = "(._qik)|(.qik)|(__pycache__)"
            return re.compile(f"^(?!{hidden_files}|{ignored_patterns}$).*$")

        @functools.cached_property
        def cwd(self) -> pathlib.Path:
            return pathlib.Path.cwd()

        @functools.cached_property
        def env(self) -> qik.venv.Env:
            return qik.venv.load()

        def restart_timer(self, interval: float = 0.1):
            if self.timer is not None:
                self.timer.cancel()

            self.timer = threading.Timer(interval, self.handle_events)
            self.timer.start()

        def on_any_event(self, event):
            with self.lock:
                try:
                    path = str(pathlib.Path(event.src_path).relative_to(self.cwd))
                    if path.endswith("qik.toml"):
                        self.runner.logger.print(
                            f"{path} config changed. Re-start watcher.",
                            emoji="construction",
                            color="red",
                        )
                        sys.exit(1)
                    elif self.qik_file_re.match(path):
                        self.changes.add(qik.dep.Glob(path))
                except ValueError:
                    path = str(pathlib.Path(event.src_path).relative_to(self.env.dir))
                    if (dist := _parse_dist(path)) and event.event_type == "created":
                        self.changes.add(qik.dep.Dist(dist))

                self.restart_timer()

        def handle_events(self):
            with self.lock:
                if self.changes:
                    if len(self.changes) == 1:
                        summary = f"Detected changes in {list(self.changes)[0]}."
                    else:
                        summary = f"Detected {len(self.changes)} changes."

                    self.runner.logger.print(summary, emoji="eyes", color="cyan", event="changes")
                    self.runner.exec(changes=self.changes)
                    self.changes = set()

    return QikEventHandler()


def start(runner: Runner):
    observer = watchdog_observers.Observer()
    handler = _make_watchdog_handler(runner=runner)
    observer.schedule(handler, ".", recursive=True)
    observer.schedule(handler, qik.venv.load().dir, recursive=True)
    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
