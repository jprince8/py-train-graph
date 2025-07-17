# py_train_graph/main.py
#!/usr/bin/env python3
"""
CLI entry point for *py‑train‑graph*.

Examples
--------
Plot up services between 03:00 and 06:00 with a one‑hour margin and show plot::

    py-train-graph routes/london_to_oxford.csv 2025-08-20 03:00 06:00 \
        -l PAD ACTONW HTRWAJN STL -m 1 --direction up

Generate images only (no popup) and include two custom spreadsheets::

    py-train-graph routes/london_to_oxford.csv 2025-08-20 05:00 07:00 \
        -l PAD ACTONW HTRWAJN STL \
        -s custom_schedules/3Q90.csv -s custom_schedules/3Q90_earlier1.csv \
        --no-show
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List
import json
from typing import Any, Dict

import tkinter as _tk
from tkinter import filedialog as _fd

from . import plot


# ---------------------------------------------------------------------------#
# Argument parsing                                                           #
# ---------------------------------------------------------------------------#


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py-train-graph",
        description="Plot distance‑time graphs from RealTimeTrains and custom schedules.",
    )

    parser.add_argument(
        "route_csv",
        type=Path,
        help="CSV mapping Location→Distance (mi).",
    )
    parser.add_argument("date", help="Date in YYYY‑MM‑DD format.")
    parser.add_argument("start_time", help="Window start (HH:MM).")
    parser.add_argument("end_time", help="Window end (HH:MM).")

    parser.add_argument(
        "-l",
        "--locations",
        nargs="+",
        required=True,
        help="GB‑NR location codes to query (space‑separated).",
    )
    parser.add_argument(
        "-m",
        "--margin-hours",
        type=int,
        default=0,
        help="Hours to extend the window before (default 0).",
    )
    parser.add_argument(
        "-s",
        "--custom_timings",
        dest="custom_timings",
        action="append",
        help="Path to a custom schedule CSV (may be used multiple times).",
    )
    parser.add_argument(
        "-d",
        "--direction",
        choices=["up", "down"],
        help="Filter by direction (optional).",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        help="Maximum number of RTT services to plot.",
    )
    parser.add_argument(
        "-a",
        "--always-include",
        nargs="+",
        default=[],
        help="Headcodes that bypass direction filtering.",
    )
    parser.add_argument(
        "--no-show",
        dest="show_plot",
        action="store_false",
        help="Suppress the interactive plot window (images still saved).",
    )
    parser.add_argument(
        "--reverse-route",
        dest="reverse_route",
        action="store_true",
        default=None,  # None = use package default
        help="Plot distances reversed (negative miles).",
    )

    return parser


# ---------------------------------------------------------------------------#
# Load preset file                                                           #
# ---------------------------------------------------------------------------#


def _choose_preset_gui(presets_dir: Path) -> Path | None:
    """Open a file‑picker in `presets_dir` and return the chosen JSON path."""
    root = _tk.Tk()
    root.withdraw()
    root.lift()
    file_path = _fd.askopenfilename(
        initialdir=str(presets_dir),
        title="Select a preset JSON",
        filetypes=[("JSON files", "*.json")],
    )
    root.destroy()
    return Path(file_path) if file_path else None


def _resolve_preset_path(preset: str) -> Path:
    """
    Resolve a preset name or path:
      • presets/name.json
      • presets/name
      • name.json
      • name

    Raises
    ------
    FileNotFoundError
        If no valid preset file is found.
    """
    presets_dir = Path("presets")
    p = Path(preset)

    # 1. If the given path exists as is, use it
    if p.exists():
        return p

    # Ensure .json suffix
    name = p.name
    if not name.lower().endswith(".json"):
        name += ".json"

    # 2. Look in presets/ directory
    candidate = presets_dir / name
    if candidate.exists():
        return candidate

    # 3. Check under given parent (e.g. presets/name)
    if p.parent and p.parent.exists():
        candidate2 = p.parent / name
        if candidate2.exists():
            return candidate2

    # Not found: error out
    raise FileNotFoundError(f"No preset file found for '{preset}' in '{presets_dir}' or as given path.")


def _load_preset(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


# ---------------------------------------------------------------------------#
# Logging                                                                    #
# ---------------------------------------------------------------------------#


def _configure_logging(verbosity: int) -> None:
    level = logging.INFO
    if verbosity == 1:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------#
# Main                                                                       #
# ---------------------------------------------------------------------------#


def main(argv: List[str] | None = None) -> None:
    # If no args passed, launch GUI to pick a preset
    if argv is None and len(sys.argv) <= 1:
        chosen = _choose_preset_gui(Path("presets"))
        if not chosen:
            sys.exit(0)
        argv = ["--preset", str(chosen)]

    # Phase 1: only parse --preset and -v
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument(
        "-p",
        "--preset",
        type=str,
        help="Name or path of a preset JSON file (omit .json if desired).",
    )
    pre.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v or -vv).",
    )
    pre_args, remaining = pre.parse_known_args(argv)

    _configure_logging(pre_args.verbose)

    if pre_args.preset:
        # load everything from JSON
        preset_path = _resolve_preset_path(pre_args.preset)
        cfg = _load_preset(preset_path)
        # merge with verbose
        cfg["show_plot"] = cfg.get("show_plot", True)
        plot.plot_services(
            distance_csv=Path(cfg["route_csv"]),
            locations=cfg["locations"],
            date_str=cfg["date"],
            start_time=cfg["start_time"],
            end_time=cfg["end_time"],
            margin_hours=cfg.get("margin_hours", 0),
            custom_timings=[Path(p) for p in cfg.get("custom_timings", [])] or None,
            limit=cfg.get("limit"),
            direction=cfg.get("direction"),
            reverse_route=cfg.get("reverse_route"),
            show_plot=cfg["show_plot"],
            always_include=cfg.get("always_include", []),
        )
        return

    parser = _build_parser()
    args = parser.parse_args(argv)

    custom_timings = [Path(p) for p in args.custom_timings] if args.custom_timings else None

    plot.plot_services(
        distance_csv=args.route_csv,
        locations=args.locations,
        date_str=args.date,
        start_time=args.start_time,
        end_time=args.end_time,
        margin_hours=args.margin_hours,
        custom_timings=custom_timings,
        limit=args.limit,
        direction=args.direction,
        reverse_route=args.reverse_route,
        show_plot=args.show_plot,
        always_include=args.always_include,
    )


if __name__ == "__main__":
    main()
