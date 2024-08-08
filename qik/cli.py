from __future__ import annotations

import argparse
import sys

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
        help="Set module name(s).",
        action="append",
        dest="modules",
    )
    parser.add_argument(
        "--watch", action="store_true", help="Watch for changes.", default=qik.unset.UNSET
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Don't read cache.",
        default=qik.unset.UNSET,
    )
    parser.add_argument("--cache", help="Set default cache.", default=qik.unset.UNSET)
    parser.add_argument(
        "--cache-when",
        help="Cache results by event type.",
        default=qik.unset.UNSET,
        choices=["success", "failed", "finished"],
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
    parser.add_argument("-p", "--profile", help="The context profile to use.", default="default")
    parser.add_argument("--since", help="Filter since git SHA.", default=qik.unset.UNSET)
    parser.add_argument(
        "--cache-type",
        help="Filter by cache type.",
        action="append",
        dest="cache_types",
    )
    parser.add_argument(
        "--cache-status",
        help="Filter by cache status.",
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
    with (
        qik.ctx.set_profile(args.profile),
        qik.ctx.set_vars(
            "qik",
            watch=args.watch,
            force=args.force,
            cache=args.cache,
            isolated=args.isolated,
            ls=args.ls,
            workers=args.workers,
            since=args.since,
            fail=args.fail,
            cache_status=args.cache_status,
            cache_when=args.cache_when,
            verbosity=args.verbosity,
            commands=args.commands or qik.unset.UNSET,
            modules=args.modules or qik.unset.UNSET,
            cache_types=args.cache_types or qik.unset.UNSET,
        ),
    ):
        res = qik.runner.exec()
        qik_ctx = qik.ctx.module("qik")

        if qik_ctx.ls:
            for cmd in sorted(res, key=lambda k: k.name):
                print(cmd.name)

        if res and qik_ctx.fail:
            sys.exit(1)
