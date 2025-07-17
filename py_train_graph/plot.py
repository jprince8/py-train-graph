# py_train_graph/plot.py
"""
High‑level plotting utilities for *py‑train‑graph*.

The public entry point is :pyfunc:`plot_services`, which plots one or more
RealTimeTrains services (plus optional user spreadsheets) on a distance‑time
graph and writes two PNG files:

* ``..._overview.png`` – small figure, high DPI (for sharing)
* ``..._zoomable.png`` – large canvas, lower DPI (for onscreen inspection)
"""

from __future__ import annotations

import logging
from datetime import datetime as _dt, time as _time
from pathlib import Path
from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

from . import config, fetch, parse, utils

__all__ = ["plot_services"]

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------#
# Distance helpers                                                           #
# ---------------------------------------------------------------------------#


def _build_distance_map(csv_path: str | Path) -> pd.DataFrame:
    """
    Return a DataFrame indexed by Location with columns:
      - Distance (mi)       (floats, negative if REVERSE_ROUTE)
      - OriginalLocation    (station name before stripping [ABC])
    """
    df = pd.read_csv(csv_path)

    # flag rows that had bracketed text
    df["OriginalLocation"] = df["Location"].copy()
    # strip out brackets
    df["Location"] = df["Location"].str.replace(r"\[.*?\]", "", regex=True).str.strip()

    # build the output DataFrame
    out = df.set_index("Location")[["Distance (mi)", "OriginalLocation"]]
    if config.REVERSE_ROUTE:
        out["Distance (mi)"] = -out["Distance (mi)"]

    # sort by distance
    out = out.sort_values("Distance (mi)")
    return out


def _draw_distance_background(ax: plt.Axes, distance_map: pd.Series) -> None:
    """Add faint horizontal lines and station labels."""
    # distance_map is the DataFrame from last time, with columns
    # ["Location", "Distance (mi)", "OriginalLocation"]
    # already sorted by distance

    distances = distance_map["Distance (mi)"].values
    locations = distance_map["OriginalLocation"].values

    ax.margins(x=0)

    tick_locs: list[float] = []
    tick_labels: list[str] = []

    for label, d in zip(locations, distances, strict=True):
        if "[" in label:  # major locations get bold colour
            # major locations
            ax.hlines(
                d,
                0,
                1,
                linestyles="dashed",
                color=config.MID_BLUE,
                alpha=0.4,
                transform=ax.get_yaxis_transform(),
            )
            tick_locs.append(d)
            tick_labels.append(label)
        else:
            # minor locations
            ax.hlines(
                d,
                0,
                1,
                linestyles="dashed",
                color=config.DARK_GREY,
                alpha=0.2,
                transform=ax.get_yaxis_transform(),
            )

    ax.set_yticks(tick_locs)
    ax.set_yticklabels(tick_labels)
    for lbl in ax.get_yticklabels():
        lbl.set_color(config.MID_BLUE)


# ---------------------------------------------------------------------------#
# Operator colour                                                             #
# ---------------------------------------------------------------------------#


def _operator_colour(operator: str) -> str:
    """Return hex colour for an operator, defaulting to 'Other'."""
    return config.OPERATOR_COLOURS.get(operator, config.OPERATOR_COLOURS["Other"])


# ---------------------------------------------------------------------------#
# Core plotting                                                              #
# ---------------------------------------------------------------------------#


def _plot_dataframe(
    ax: plt.Axes,
    times: Iterable[pd.Timestamp],
    dist: Iterable[float],
    *,
    headcode: str,
    color: str,
    linewidth: float = 1.0,
    marker_size: float = 3.0,
    direction: str,
    end_time: _time,
) -> None:
    """Plot a single service and label its last point."""
    times_list = list(times)
    dist_list = list(dist)

    ax.plot(
        times_list,
        dist_list,
        marker="o",
        markersize=marker_size,
        linestyle="-",
        linewidth=linewidth,
        color=color,
        label=headcode,
    )
    utils.label_last_point(
        ax,
        end_time,
        times_list,
        dist_list,
        headcode,
        color,
        direction,
    )


# ---------------------------------------------------------------------------#
# Public API                                                                 #
# ---------------------------------------------------------------------------#


def plot_services(
    distance_csv: str | Path,
    locations: list[str],
    date_str: str,
    start_time: str,
    end_time: str,
    margin_hours: int = 0,
    *,
    custom_timings: list[str | Path] | None = None,
    limit: int | None = None,
    direction: str | None = None,  # 'up' or 'down'
    reverse_route: bool | None = None,
    show_plot: bool | None = None,
    always_include: list[str] | None = None,
) -> None:
    """
    Plot RealTimeTrains services and optional CSV schedules.

    Parameters
    ----------
    always_include
        Headcodes that skip the direction filter regardless of *direction*.

    Images are written to :pydata:`config.OUTPUT_DIR` with timestamped filenames.
    """
    reverse_route = config.REVERSE_ROUTE if reverse_route is None else reverse_route
    show_plot = config.SHOW_PLOT if show_plot is None else show_plot
    always_include = [hc.upper() for hc in always_include or []]

    # ---------------------------------------------------------------------#
    # Prepare data                                                         #
    # ---------------------------------------------------------------------#
    distance_map = _build_distance_map(distance_csv)

    base_urls = utils.generate_rtt_urls(
        locations, date_str, start_time, end_time, margin_hours
    )

    # Gather all detailed service links
    detail_urls: list[str] = []
    for search_url in base_urls:
        html = fetch.get_html(search_url)
        detail_urls.extend(parse.fetch_service_links(html))

    start_dt = _dt.strptime(start_time, "%H:%M").time()
    end_dt = _dt.strptime(end_time, "%H:%M").time()

    # ---------------------------------------------------------------------#
    # Create figure                                                        #
    # ---------------------------------------------------------------------#
    if show_plot:
        plt.ion()
    fig, ax = plt.subplots(figsize=config.OVERVIEW_FIGSIZE)
    ax.grid(True, axis="x", alpha=0.5)
    _draw_distance_background(ax, distance_map)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%D/%M %H:%M"))
    fig.autofmt_xdate()
    ax.set_xlabel("Time")
    ax.set_ylabel("Distance (mi)")
    ax.set_title("Loading services...", fontsize=14, fontweight='bold')
    base_date = _dt.strptime(date_str, "%Y-%m-%d").date()
    ax.set_xlim(
        _dt.combine(base_date, start_dt),
        _dt.combine(base_date, end_dt),
    )

    plotted: list[tuple[str, str]] = []  # (headcode, source)
    seen_urls: list[str] = []

    # ---------------------------------------------------------------------#
    # Plot RTT services                                                    #
    # ---------------------------------------------------------------------#
    for url in tqdm(detail_urls, desc="RTT services", unit="service"):
        if limit is not None and len(plotted) >= limit:
            break

        if url in seen_urls:
            continue
        seen_urls.append(url)

        html = fetch.get_html(url)
        start_date, headcode, operator, is_bus = parse.fetch_service_metadata(html)

        if is_bus:
            continue
        headcode_upper = headcode.upper()
        if operator in config.IGNORE_OPERATORS:
            continue
        colour = _operator_colour(operator)

        if start_date is None:
            raise ValueError(start_date)

        df = parse.parse_service_page(html, distance_map, start_date)
        if df.empty:
            continue

        # Filter window
        times: list[pd.Timestamp] = []
        visible_times: list[pd.Timestamp] = []
        dist: list[float] = []
        visible_dist: list[float] = []
        for _, row in df.iterrows():
            for tm in (row["Arr"], row["Dep"]):
                if pd.notnull(tm):
                    times.append(tm)
                    dist.append(row["Distance"])
                    if start_dt <= tm.time() <= end_dt:
                        visible_times.append(tm)
                        visible_dist.append(row["Distance"])

        if not visible_times:
            continue

        # direction filter unless headcode always included
        if direction and headcode_upper not in always_include:
            diffs = np.diff(visible_dist)
            if reverse_route:
                if direction == "up" and not np.any(diffs > 0):
                    continue
                if direction == "down" and not np.any(diffs < 0):
                    continue
            else:
                if direction == "up" and not np.any(diffs < 0):
                    continue
                if direction == "down" and not np.any(diffs > 0):
                    continue

        _plot_dataframe(
            ax,
            times,
            dist,
            headcode=headcode,
            color=colour,
            linewidth=1.0,
            marker_size=3.0,
            direction=direction or "up",
            end_time=end_dt,
        )
        plotted.append((headcode, url))
        # live update
        if show_plot:
            fig.canvas.draw()
            plt.pause(0.001)

    # ---------------------------------------------------------------------#
    # Plot custom spreadsheets                                             #
    # ---------------------------------------------------------------------#
    custom_headcodes = []
    if custom_timings and config.USE_CUSTOM:
        custom_colours = iter(["#ff0000", "#ffaa00", "#00ff00", "#00aaff", "#aa00ff"])

        for path in custom_timings:
            df = parse.parse_manual_csv(path, distance_map, date_str)
            if df.empty:
                continue

            # Filter to window
            mask = df["Time"].apply(lambda t: start_dt <= t.time() <= end_dt)
            df_window = df.loc[mask]

            if df_window.empty:
                continue

            headcode = Path(path).stem
            headcode_upper = headcode.upper()

            # direction filter unless headcode always included
            if direction and headcode_upper not in always_include:
                diffs = np.diff(df["Distance"])
                if reverse_route:
                    if direction == "up" and not np.all(diffs >= 0):
                        continue
                    if direction == "down" and not np.all(diffs <= 0):
                        continue
                else:
                    if direction == "up" and not np.all(diffs <= 0):
                        continue
                    if direction == "down" and not np.all(diffs >= 0):
                        continue

            colour = next(custom_colours)
            _plot_dataframe(
                ax,
                df["Time"],
                df["Distance"],
                headcode=headcode,
                color=colour,
                linewidth=2.0,
                marker_size=4.0,
                direction=direction or "up",
                end_time=end_dt,
            )
            plotted.append((headcode, str(path)))
            custom_headcodes.append(headcode)
            if show_plot:
                fig.canvas.draw()
                plt.pause(0.001)

    if not plotted:
        _LOG.warning("No services plotted — nothing to save")
        return

    # ---------------------------------------------------------------------#
    # Finalise plot                                                        #
    # ---------------------------------------------------------------------#
    plt.subplots_adjust(left=0.12, right=0.98, top=0.96, bottom=0.1)
    # Add a descriptive title: Route name, date, time window & headcodes
    route_name = Path(distance_csv).stem.replace('_', ' ').title()
    time_range = f"{start_time}–{end_time}"
    headcodes_joined = ", ".join(custom_headcodes)
    title_text = f"{route_name} | {date_str} | {time_range} | Services: {headcodes_joined}"
    ax.set_title(title_text, fontsize=14, fontweight='bold')

    # ---------------------------------------------------------------------#
    # Save images                                                          #
    # ---------------------------------------------------------------------#
    # build descriptive filename: route, time window, direction, and timestamp
    headcodes_joined = "_"+"_".join(custom_headcodes)
    route_name = Path(distance_csv).stem
    time_range = f"{start_time.replace(':', '')}-{end_time.replace(':', '')}"
    dir_tag = direction or "all"
    filename_base = f"{route_name}_{date_str}_{time_range}_{dir_tag}{headcodes_joined}"

    # Overview (small, high DPI)
    overview_path = (
        config.OUTPUT_DIR / f"{filename_base}_overview.png"
    )
    fig.set_size_inches(*config.OVERVIEW_FIGSIZE)
    fig.savefig(overview_path, dpi=config.OVERVIEW_DPI, bbox_inches="tight")

    # Zoomable (large canvas, low DPI)
    fig.set_size_inches(*config.ZOOMABLE_FIGSIZE)
    zoom_path = (
        config.OUTPUT_DIR / f"{filename_base}_zoomable.png"
    )
    fig.savefig(zoom_path, dpi=config.ZOOMABLE_DPI, bbox_inches="tight")

    _LOG.info("Saved overview image → %s", overview_path)
    _LOG.info("Saved zoomable image → %s", zoom_path)

    # ---------------------------------------------------------------------#
    # Show or close                                                        #
    # ---------------------------------------------------------------------#
    if show_plot:
        fig.set_size_inches(*config.OVERVIEW_FIGSIZE)
        plt.ioff()  # turn interactive off
        plt.show()
    else:
        plt.close(fig)
