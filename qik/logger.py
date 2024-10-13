from __future__ import annotations

import collections
import contextlib
import os
import pathlib
from typing import IO, TYPE_CHECKING, Iterator, Literal, TypeAlias

import msgspec

import qik.conf
import qik.console
import qik.ctx
import qik.file
import qik.func

if TYPE_CHECKING:
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


@qik.func.cache
def out_dir() -> pathlib.Path:
    # Note, relative_to(walk_up=True) is supported in python 3.12.
    return pathlib.Path(os.path.relpath(qik.conf.priv_work_dir() / "out", os.getcwd()))


class Manifest(msgspec.Struct):
    cmd_status: dict[str, RunStatus]
    runnables: list[str]
    runnable_status: dict[str, RunStatus]
    cached_runnables: list[str]


class Stats:
    def __init__(self, graph: Graph):
        self.manifest_path = out_dir() / "manifest.json"

        # Command-level status information
        self.cmd_finished: dict[str, int] = collections.defaultdict(int)
        self.cmd_running: dict[str, bool] = collections.defaultdict(bool)
        self.cmd_total: dict[str, int] = collections.defaultdict(int)
        for runnable in graph:
            self.cmd_total[runnable.cmd] += 1

        self.cmd_status: dict[str, RunStatus] = collections.defaultdict(lambda: "pending")

        # Runnable-level status information
        self.runnables = [runnable.name for runnable in graph]
        self.runnable_status: dict[str, RunStatus] = {
            runnable.name: "pending" for runnable in graph
        }
        self.cached_runnables = []

    @property
    def run_failed(self) -> bool:
        return any(status == "failed" for status in self.cmd_status.values())

    def start(self, runnable: Runnable) -> None:
        self.cmd_running[runnable.cmd] = True

    def finish(
        self, runnable: Runnable, *, result: Result | None, cache_entry: Entry | None
    ) -> None:
        # Track runnable status
        if not result:
            self.runnable_status[runnable.name] = "skipped"
        elif result.code != 0:
            self.runnable_status[runnable.name] = "failed"
        else:
            self.runnable_status[runnable.name] = "success"

        if cache_entry:
            self.cached_runnables.append(runnable.name)

        # Track command status
        self.cmd_finished[runnable.cmd] += 1

        if self.cmd_finished[runnable.cmd] >= self.cmd_total[runnable.cmd]:
            self.cmd_running[runnable.cmd] = False

        if self.cmd_status[runnable.cmd] == "pending":
            if not result:
                self.cmd_status[runnable.cmd] = "skipped"
            elif result.code != 0:
                self.cmd_status[runnable.cmd] = "failed"
            elif self.cmd_finished[runnable.cmd] >= self.cmd_total[runnable.cmd]:
                self.cmd_status[runnable.cmd] = "success"

    def write(self) -> None:
        qik.file.write(
            self.manifest_path,
            msgspec.json.encode(
                Manifest(
                    runnables=self.runnables,
                    cmd_status=self.cmd_status,
                    cached_runnables=self.cached_runnables,
                    runnable_status=self.runnable_status,
                )
            ),
        )


class Logger:
    def __init__(self):
        self._reset_state()
        self.num_runs = 0

    def _reset_state(self) -> None:
        self.graph = None
        log_files: dict[str, IO[str]] = getattr(self, "_log_files", {})
        for file in log_files.values():
            file.close()
        self._log_files = {}
        self._stats: Stats | None = None

    def _get_log_file(self, runnable: Runnable) -> IO[str]:
        if runnable.name not in self._log_files:
            path = out_dir() / f"{runnable.name}.out"
            self._log_files[runnable.name] = qik.file.open(path, "w")

        return self._log_files[runnable.name]

    @property
    def stats(self) -> Stats:
        if not self._stats:
            raise AssertionError("Stats not initialized")

        return self._stats

    @stats.setter
    def stats(self, stats: Stats) -> None:
        self._stats = stats

    @contextlib.contextmanager
    def run(self, graph: Graph) -> Iterator[None]:
        self.graph = graph
        self.stats = Stats(graph)
        self.stats.write()
        self.handle_run_started()
        try:
            yield
        finally:
            self.handle_run_finished()
            self.stats.write()
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
                if msg := msg.strip():
                    self._get_log_file(runnable).write(msg)
            elif event == "start":
                self.stats.start(runnable)
            elif event == "finish":
                self.stats.finish(runnable, result=result, cache_entry=cache_entry)

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
        if self.num_runs and self.graph:
            qik.console.rule(color="white")

        self.num_runs += 1

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
            if msg := msg.strip():
                qik.console.print(msg, emoji=emoji, color=color, style=None)
        elif event == "start" or (event == "finish" and not result):
            qik.console.rule(msg, emoji=emoji, color=color)
        else:
            kwargs = {"overflow": "ellipsis", "no_wrap": True} if event == "finish" else {}
            qik.console.print(msg, emoji=emoji, color=color, **kwargs)

        if event == "exception":
            qik.console.print_exception()


class HideableBarColumn(rich_progress.BarColumn):
    def render(self, task) -> RenderableType:  # type: ignore
        if task.fields.get("show_progress", True):
            return super().render(task)
        return rich_text.Text("")


class HideableSpinnerColumn(rich_progress.SpinnerColumn):
    def render(self, task) -> RenderableType:
        if task.fields.get("show_progress", True):
            return super().render(task)
        return rich_text.Text("")


class Progress(Logger):
    """Logs live progress bars and prints output at end."""

    def __init__(self):
        super().__init__()
        self.status: RunStatus = "pending"

    def get_status_text(self) -> str:
        status_text = f"Output in [bold]{out_dir()}"
        if self.status == "pending":
            status_text = f":heavy_minus_sign-emoji: [cyan]{status_text}"
        elif self.status == "success":
            status_text = f":white_check_mark-emoji: [green]{status_text}"
        elif self.status == "failed":
            status_text = f":broken_heart-emoji: [red]{status_text}"

        return status_text

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

        if self.status == "pending":
            table.add_row(self.get_status_text())

        return table

    def handle_run_started(self) -> None:
        super().handle_run_started()

        self.status = "pending"
        self.progress = rich_progress.Progress(
            rich_progress.TextColumn("{task.description}"),
            HideableBarColumn(complete_style="cyan"),
            HideableSpinnerColumn(style="cyan"),
            expand=True,
        )

        self.cmds = {
            cmd: self.progress.add_task(
                f":heavy_minus_sign-emoji: [dim]{cmd}",
                total=self.stats.cmd_total[cmd],
                show_progress=False,
            )
            for cmd in sorted(self.stats.cmd_total)
        }
        self.captured: dict[str, list[str]] = collections.defaultdict(list)

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
            match self.stats.cmd_status[runnable.cmd]:
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
                show_progress=self.stats.cmd_running[runnable.cmd],
            )
            self.live.update(self.generate_table())
        elif event == "exception":
            qik.console.print(msg, emoji=emoji, color=color)
            qik.console.print_exception()
        elif event != "output":
            qik.console.print(msg, emoji=emoji, color=color)
        elif runnable:
            self.captured[runnable.name].append(msg)

    def handle_run_finished(self) -> None:
        self.status = "failed" if self.stats.run_failed else "success"
        self.live.update(self.generate_table())
        self.live.stop()

        verbosity = qik.ctx.by_namespace("qik").verbosity
        if verbosity:
            cached_runnables = self.stats.cached_runnables

            for name in sorted(self.stats.runnables):
                match self.stats.runnable_status[name]:
                    case "success":
                        emoji = (
                            "fast-forward_button"
                            if name in cached_runnables
                            else "white_check_mark"
                        )
                        color = "green"
                        show = True if verbosity > 1 else False
                        output = "\n".join(line.strip() for line in self.captured[name])
                    case "failed":
                        emoji = (
                            "fast-forward_button" if name in cached_runnables else "broken_heart"
                        )
                        color = "red"
                        show = True if verbosity > 0 else False
                        output = "\n".join(line.strip() for line in self.captured[name])
                    case _:
                        emoji = "heavy_minus_sign"
                        color = "yellow"
                        show = True if verbosity > 1 else False
                        output = "[dim][italic]Skipped"

                if show:
                    qik.console.rule(f":{emoji}-emoji: [{color}]{name}", color=color)
                    output = output or "[dim][italic]No output"
                    qik.console.print(output)

        qik.console.print(self.get_status_text())
