from __future__ import annotations

import collections
import contextlib
import functools
from typing import IO, TYPE_CHECKING, Iterator, Literal, TypeAlias

import msgspec

import qik.conf
import qik.console
import qik.file

if TYPE_CHECKING:
    import pathlib

    import rich.live as rich_live
    import rich.progress as rich_progress
    import rich.table as rich_table
    import rich.text as rich_text
    from rich.console import RenderableType

    from qik.cache import Entry
    from qik.runnable import Result, Runnable
    from qik.runner import Graph

    Event: TypeAlias = Literal["start", "changes", "finish", "exception", "output"]
    from qik.console import Color, Emoji
else:
    import qik.lazy

    rich_progress = qik.lazy.module("rich.progress")
    rich_style = qik.lazy.module("rich.style")
    rich_table = qik.lazy.module("rich.table")
    rich_text = qik.lazy.module("rich.text")
    rich_live = qik.lazy.module("rich.live")

RunStatus: TypeAlias = Literal["success", "failed", "skipped", "pending"]


@functools.cache
def out_dir() -> pathlib.Path:
    return qik.conf.priv_work_dir(relative=True) / "out"


class Manifest(msgspec.Struct):
    runnables: list[str]
    status: dict[str, RunStatus]


class CmdStats:
    def __init__(self, graph: Graph):
        self.manifest_path = out_dir() / "manifest.json"
        self.runnables = [runnable.name for runnable in graph]
        self.running: dict[str, bool] = collections.defaultdict(bool)
        self.total: dict[str, int] = collections.defaultdict(int)
        for runnable in graph:
            self.total[runnable.cmd] += 1

        self.finished: dict[str, int] = collections.defaultdict(int)
        self.status: dict[str, RunStatus] = collections.defaultdict(lambda: "pending")

    @property
    def failed(self) -> bool:
        return any(status == "failed" for status in self.status.values())

    def start(self, runnable: Runnable) -> None:
        self.running[runnable.cmd] = True

    def finish(self, runnable: Runnable, result: Result | None) -> None:
        self.finished[runnable.cmd] += 1

        if self.finished[runnable.cmd] >= self.total[runnable.cmd]:
            self.running[runnable.cmd] = False

        if self.status[runnable.cmd] == "pending":
            if not result:
                self.status[runnable.cmd] = "skipped"
            elif result.code != 0:
                self.status[runnable.cmd] = "failed"
            elif self.finished[runnable.cmd] >= self.total[runnable.cmd]:
                self.status[runnable.cmd] = "success"

    def write(self) -> None:
        qik.file.write(
            self.manifest_path,
            msgspec.json.encode(Manifest(runnables=self.runnables, status=self.status)),
        )


class Logger:
    def __init__(self):
        self._reset_state()

    def _reset_state(self) -> None:
        self.graph = None
        log_files: dict[str, IO[str]] = getattr(self, "_log_files", {})
        for file in log_files.values():
            file.close()
        self._log_files = {}
        self.cmd_stats: CmdStats | None = None

    def _get_log_file(self, runnable: Runnable) -> IO[str]:
        if runnable.name not in self._log_files:
            path = out_dir() / f"{runnable.name}.out"
            self._log_files[runnable.name] = qik.file.open(path, "w")

        return self._log_files[runnable.name]

    @contextlib.contextmanager
    def run(self, graph: Graph) -> Iterator[None]:
        self.graph = graph
        self.cmd_stats = CmdStats(graph)
        self.cmd_stats.write()
        self.handle_run_started()
        try:
            yield
        finally:
            self.handle_run_finished()
            self.cmd_stats.write()
            self._reset_state()

    def print(
        self,
        msg: str,
        runnable: Runnable | None = None,
        cache_entry: Entry | None = None,
        result: Result | None = None,
        event: Event | None = None,
        emoji: Emoji | None = None,
        color: Color | None = None,
    ) -> None:
        if runnable:
            if event == "output":
                self._get_log_file(runnable).write(msg)
            elif event == "start":
                self.cmd_stats.start(runnable)
            elif event == "finish":
                self.cmd_stats.finish(runnable, result)

        self.handle_output(
            msg,
            runnable=runnable,
            cache_entry=cache_entry,
            result=result,
            event=event,
            emoji=emoji,
            color=color,
        )

    def handle_run_started(self) -> None:
        pass

    def handle_run_finished(self) -> None:
        pass

    def handle_output(
        self,
        msg: str,
        runnable: Runnable | None = None,
        cache_entry: Entry | None = None,
        result: Result | None = None,
        event: Event | None = None,
        emoji: Emoji | None = None,
        color: Color | None = None,
    ) -> None:
        pass


class Stdout(Logger):
    """Logs command results to stdout."""

    def __init__(self):
        super().__init__()
        self.num_runs = 0

    def handle_run_started(self) -> None:
        if self.num_runs and self.graph:
            qik.console.rule()

        self.num_runs += 1

    def handle_output(
        self,
        msg: str,
        runnable: Runnable | None = None,
        cache_entry: Entry | None = None,
        result: Result | None = None,
        event: Event | None = None,
        emoji: Emoji | None = None,
        color: Color | None = None,
    ) -> None:
        """Print output from a runnable."""
        if event == "output":
            print_kwargs = {"end": "", "highlight": False, "style": None}
        else:
            print_kwargs = {}

        qik.console.print(msg, emoji=emoji, color=color, **print_kwargs)

        if event == "exception":
            qik.console.print_exception()


class HideableBarColumn(rich_progress.BarColumn):
    def render(self, task) -> RenderableType:
        if task.fields.get("show_progress", True):
            return super().render(task)
        return rich_text.Text("")


class HideableSpinnerColumn(rich_progress.SpinnerColumn):
    def render(self, task) -> RenderableType:
        if task.fields.get("show_progress", True):
            return super().render(task)
        return rich_text.Text("")


class Progress(Logger):
    """Logs live progress bars while storing results in the .qik/run folder."""

    def __init__(self):
        super().__init__()
        self.status: RunStatus = "pending"

    def generate_table(self):
        table = rich_table.Table.grid(padding=(0, 1))
        table.add_row(self.progress)

        status_text = f"Output in [bold]{out_dir()}"
        if self.status == "pending":
            status_text = f":heavy_minus_sign-emoji: [cyan]{status_text}"
        elif self.status == "success":
            status_text = f":white_check_mark-emoji: [green]{status_text}"
        elif self.status == "failed":
            status_text = f":broken_heart-emoji: [red]{status_text}"
        table.add_row(status_text)
        return table

    def handle_run_started(self) -> None:
        self.status = "pending"
        self.progress = rich_progress.Progress(
            rich_progress.TextColumn("{task.description}"),
            HideableBarColumn(complete_style="cyan"),
            HideableSpinnerColumn(style="cyan"),
            expand=True,
        )

        self.cmds = {
            cmd: self.progress.add_task(
                f":heavy_minus_sign-emoji: [dim]{cmd}", total=count, show_progress=False
            )
            for cmd, count in self.cmd_stats.total.items()
        }

        self.live = rich_live.Live(
            self.generate_table(), refresh_per_second=10, console=qik.console.get()
        )
        self.live.start()

    def handle_output(
        self,
        msg: str,
        runnable: Runnable | None = None,
        cache_entry: Entry | None = None,
        result: Result | None = None,
        event: Event | None = None,
        emoji: Emoji | None = None,
        color: Color | None = None,
    ) -> None:
        """Print output from a runnable."""
        if event == "start" and runnable:
            self.progress.update(
                self.cmds[runnable.cmd],
                description=f":construction-emoji: [bold blue]{runnable.cmd}",
                show_progress=True,
            )
        elif event == "finish" and runnable:
            match self.cmd_stats.status[runnable.cmd]:
                case "skipped":
                    status = ":heavy_minus_sign-emoji:[yellow]"
                case "failed":
                    status = ":broken_heart-emoji:[red]"
                case "success":
                    status = ":white_check_mark-emoji:[green]"
                case "pending":
                    status = ":construction-emoji:[bold blue]"

            self.progress.update(
                self.cmds[runnable.cmd],
                advance=1,
                description=f"{status} {runnable.cmd}",
                show_progress=self.cmd_stats.running[runnable.cmd],
            )
            self.live.update(self.generate_table())
        elif event == "exception":
            qik.console.print(msg, emoji=emoji, color=color)
            qik.console.print_exception()
        elif event != "output":
            qik.console.print(msg, emoji=emoji, color=color)

    def handle_run_finished(self) -> None:
        self.status = "failed" if self.cmd_stats.failed else "success"
        self.live.update(self.generate_table())
        self.live.stop()
