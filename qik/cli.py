from __future__ import annotations

import argparse
import os
import pathlib
import sys

import qik.conf
import qik.ctx
import qik.runner
import qik.unset


def main() -> None:
    """The main entrypoint into the CLI."""
    parser = argparse.ArgumentParser()

    parser.add_argument("commands", help="Command name(s)", nargs="*")
    parser.add_argument(
        "-m",
        "--module",
        help="Select commands by module(s).",
        action="append",
        dest="modules",
    )
    parser.add_argument(
        "-s",
        "--space",
        help="Select commands by space(s).",
        action="append",
        dest="spaces",
    )
    parser.add_argument(
        "--watch", action="store_true", help="Watch for changes.", default=qik.unset.UNSET
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Don't read caches.",
        default=qik.unset.UNSET,
    )
    parser.add_argument(
        "-n", "--workers", help="Number of workers.", type=int, default=qik.unset.UNSET
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Don't run dependent commands.",
        default=qik.unset.UNSET,
    )
    parser.add_argument(
        "--ls", action="store_true", help="List selected commands.", default=qik.unset.UNSET
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Fail if any commands are selected.",
        default=qik.unset.UNSET,
    )
    parser.add_argument("--since", help="Select since git SHA.", default=qik.unset.UNSET)
    parser.add_argument(
        "--cache",
        help="Select by cache(s).",
        action="append",
        dest="caches",
    )
    parser.add_argument(
        "--cache-status",
        help="Select by cache status.",
        default=qik.unset.UNSET,
        choices=["warm", "cold"],
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        nargs="?",
        const=2,
        default=qik.unset.UNSET,
        type=int,
        help="Set verbosity (1 by default, 2 if -v is present, or specify level)",
    )

    args = parser.parse_args()
    spaces = args.spaces

    # Set the space if in a space root
    if not spaces and pathlib.Path.cwd() != qik.conf.root():
        location = (
            str(pathlib.Path.cwd().relative_to(qik.conf.root())).replace(os.path.sep, "/") + "/"
        )
        for space_name, space_conf in qik.conf.project().spaces.items():
            if space_conf.root and location.startswith(space_conf.root):
                spaces = [space_name]
                break

    with qik.ctx.set_vars(
        "qik",
        watch=args.watch,
        force=args.force,
        isolated=args.isolated,
        ls=args.ls,
        workers=args.workers,
        since=args.since,
        fail=args.fail,
        cache_status=args.cache_status,
        verbosity=args.verbosity,
        commands=args.commands or qik.unset.UNSET,
        modules=args.modules or qik.unset.UNSET,
        spaces=spaces or qik.unset.UNSET,
        caches=args.caches or qik.unset.UNSET,
    ):
        res = qik.runner.exec()
        qik_ctx = qik.ctx.by_namespace("qik")

        if qik_ctx.ls:
            for cmd in sorted(res, key=lambda k: k.name):
                print(cmd.name)

        if res and qik_ctx.fail:
            sys.exit(1)
