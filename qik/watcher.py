"""Core watching functionality.

Note that we have an integration test for this in test_integration.py::test_watch,
however coverage is not yet instrumented for it (hence pragma: no covers)
"""

from __future__ import annotations

import fnmatch
import pathlib
import re
import sys
import threading
from typing import TYPE_CHECKING

import qik.dep
import qik.func
import qik.space
import qik.unset

if TYPE_CHECKING:
    import watchdog.events as watchdog_events
    import watchdog.observers as watchdog_observers

    import qik.venv
    from qik.runner import Runner

    class QikEventHandlerProtocol(watchdog_events.FileSystemEventHandler):
        active_venv: qik.venv.Active | None
else:
    import qik.lazy

    watchdog_events = qik.lazy.module("watchdog.events")
    watchdog_observers = qik.lazy.module("watchdog.observers")


@qik.func.cache
def _parse_pydist(path: str) -> None | str:
    match = re.match(r"^(.+)-([^-]+)\.dist-info/RECORD$", path)

    # The pip installation process seems to use "~" as a temporary marker
    # for package names
    if match and not match.group(1).startswith("~"):
        return qik.dep._normalize_pydist_name(match.group(1))


def _make_watchdog_handler(*, runner: Runner) -> QikEventHandlerProtocol:  # pragma: no cover
    """Create the watchdog event handler.

    Watch for both internal project and virtual env changes.

    Note that we create the class in the function to avoid invoking
    a lazy watchdog import.
    """

    class QikEventHandler(watchdog_events.FileSystemEventHandler):
        def __init__(self):
            self.timer: threading.Timer | None = None
            self.changes: set[qik.dep.Dep] = set()
            self.runner = runner
            self.lock = threading.Lock()

        @qik.func.cached_property
        def qik_file_re(self) -> re.Pattern:
            hidden_files = f"({fnmatch.translate('**/.*')})|({fnmatch.translate('.*')})"
            ignored_patterns = "(__pycache__)"
            return re.compile(f"^(?!{hidden_files}|{ignored_patterns}$).*$")

        @qik.func.cached_property
        def cwd(self) -> pathlib.Path:
            return pathlib.Path.cwd()

        @qik.func.cached_property
        def active_venv(self) -> qik.venv.Active | None:
            # Find if an active venv is being used by the runner. IF so, we'll watch it.
            for runnable in self.runner.graph:
                if isinstance(runnable.resolved_venv, qik.venv.Active):
                    return runnable.resolved_venv

        def restart_timer(self, interval: float = 0.1):
            if self.timer is not None:
                self.timer.cancel()

            self.timer = threading.Timer(interval, self.handle_events)
            self.timer.start()

        def on_any_event(self, event):
            if not isinstance(
                event,
                (
                    watchdog_events.FileModifiedEvent,
                    watchdog_events.FileCreatedEvent,
                    watchdog_events.FileDeletedEvent,
                    watchdog_events.FileMovedEvent,
                ),
            ):
                return

            with self.lock:
                src_path = pathlib.Path(event.src_path).resolve()
                try:
                    path = str(src_path.relative_to(self.cwd))
                    if path.endswith("qik.toml"):
                        self.runner.logger.print(
                            f"{path} config changed. Please restart watcher.",
                            emoji="construction",
                            color="red",
                        )
                        sys.exit(1)
                    elif self.qik_file_re.match(path):
                        self.changes.add(qik.dep.Glob(path))
                except ValueError:
                    if self.active_venv:
                        try:
                            path = str(src_path.relative_to(self.active_venv.site_packages_dir))
                            if (pydist := _parse_pydist(path)) and event.event_type == "created":
                                self.changes.add(qik.dep.Pydist(pydist))
                        except ValueError:  # Not part of the venv
                            pass

                self.restart_timer()

        def handle_events(self):
            with self.lock:
                if self.changes:
                    if len(self.changes) <= 5:
                        changes = ", ".join(str(c) for c in self.changes)
                        summary = f"Detected changes in {changes}."
                    else:
                        summary = f"Detected {len(self.changes)} changes."

                    self.runner.logger.print(summary, emoji="eyes", color="cyan", event="changes")
                    self.runner.exec(changes=self.changes)
                    self.changes = set()

    return QikEventHandler()  # type: ignore


def start(runner: Runner):  # pragma: no cover
    observer = watchdog_observers.Observer()
    handler = _make_watchdog_handler(runner=runner)
    observer.schedule(handler, ".", recursive=True)
    if handler.active_venv:
        observer.schedule(handler, str(handler.active_venv.site_packages_dir), recursive=True)

    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
