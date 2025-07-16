# py_train_graph/utils.py
"""
General‑purpose helper functions used across the *py‑train‑graph* package.

These utilities are deliberately free of Matplotlib, Requests and other
heavy dependencies where possible, making them easy to unit‑test.
"""

from __future__ import annotations

import hashlib
from datetime import datetime as _dt, timedelta, time as _time
from typing import Iterable

import pandas as pd

from . import config

__all__ = [
    "parse_hhmm_half",
    "url_to_filename",
    "generate_rtt_urls",
    "label_last_point",
]

# ---------------------------------------------------------------------------#
# Time helpers                                                               #
# ---------------------------------------------------------------------------#


def parse_hhmm_half(text: str | float | int | None) -> pd.Timestamp | None:
    """
    Convert 'HHMM', 'HHMM½' or NaN to a pandas `Timestamp`.

    Examples
    --------
    >>> parse_hhmm_half("1234")
    Timestamp('1900-01-01 12:34:00')
    >>> parse_hhmm_half("1234½")
    Timestamp('1900-01-01 12:34:30')
    """
    if pd.isna(text):
        return None
    text = str(text).strip().replace("½", ".5")
    try:
        if "." in text:
            return pd.to_datetime(text, format="%H%M.%f")
        return pd.to_datetime(text, format="%H%M")
    except Exception:
        return None


# ---------------------------------------------------------------------------#
# File‑system helpers                                                        #
# ---------------------------------------------------------------------------#


def url_to_filename(url: str) -> str:
    """
    Create a deterministic MD5‑based filename from a URL.

    Ensures cached HTML files have predictable, filesystem‑safe names.
    """
    return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest() + ".html"


# ---------------------------------------------------------------------------#
# RealTimeTrains URL generator                                               #
# ---------------------------------------------------------------------------#


def generate_rtt_urls(
    locations: list[str],
    date: str,
    start_time: str,
    end_time: str,
    margin_hours: int = 0,
) -> list[str]:
    """
    Build a list of RealTimeTrains detailed search URLs.

    Extends only the start time by margin_hours. If the extended start
    falls before 00:00 of `date`, splits into two URLs:
      - One for the previous date covering [extended_start, 23:59]
      - One for `date` covering [00:00, end_time]

    Parameters
    ----------
    locations
        List of three‑ or four‑letter GB‑NR location codes.
    date
        Date string in 'YYYY‑MM‑DD' format.
    start_time, end_time
        Window start/end in 'HH:MM'.
    margin_hours
        Hours to extend the window at start.

    Returns
    -------
    List[str]
        One URL per location.
    """
    fmt = "%H:%M"
    date_obj = _dt.strptime(date, "%Y-%m-%d").date()
    start_dt = _dt.strptime(start_time, fmt) - timedelta(hours=margin_hours)
    end_dt = _dt.strptime(end_time, fmt)

    urls: list[str] = []
    end_str = min(end_dt, _dt.strptime("23:59", fmt)).strftime("%H%M")
    midnight = _dt.strptime("00:00", fmt)

    for loc in locations:
        if start_dt < midnight:
            # previous-day segment
            prev_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
            start_prev = start_dt.strftime("%H%M")
            urls.append(
                config.RTT_DETAILED_URL.format(
                    loc=loc,
                    date=prev_date,
                    start=start_prev,
                    end="2359",
                )
            )
            # current-day segment
            urls.append(
                config.RTT_DETAILED_URL.format(
                    loc=loc,
                    date=date,
                    start="0000",
                    end=end_str,
                )
            )
        else:
            start_str = min(start_dt, _dt.strptime("23:59", fmt)).strftime("%H%M")
            urls.append(
                config.RTT_DETAILED_URL.format(
                    loc=loc,
                    date=date,
                    start=start_str,
                    end=end_str,
                )
            )

    return urls


# ---------------------------------------------------------------------------#
# Plot annotation helper                                                     #
# ---------------------------------------------------------------------------#

# Matplotlib only imported lazily to avoid heavy dependency for pure logic tests
import matplotlib.axes as _maxes  # noqa: E402


def label_last_point(
    ax: _maxes.Axes,
    end_time: _time,
    times: Iterable[pd.Timestamp],
    dist: Iterable[float],
    headcode: str,
    color: str,
    direction: str,
    *,
    reverse_route: bool | None = None,
) -> None:
    """
    Annotate the last visible point on the current x‑axis with its headcode.

    Parameters
    ----------
    ax
        Target Matplotlib `Axes`.
    end_time
        Window end as `datetime.time`; used to pick last point within window.
    times, dist
        Iterables of timestamps and matching distances.
    headcode
        Train headcode text to display.
    color
        Text colour (matches line colour).
    direction
        'up' or 'down' — influences text vertical alignment.
    reverse_route
        If `True`, distances are plotted negative; affects label alignment.
        Defaults to `config.REVERSE_ROUTE` if `None`.
    """
    reverse_route = config.REVERSE_ROUTE if reverse_route is None else reverse_route

    times = list(times)
    dist = list(dist)
    if not times:
        return

    # Determine text alignment based on route direction
    if reverse_route:
        va = "bottom" if direction == "up" else "top"
        offset = 0.2 if direction == "up" else -0.2
    else:
        va = "top" if direction == "up" else "bottom"
        offset = -0.2 if direction == "up" else 0.2

    # Index of last point within the visible window
    idx = max(
        (i for i, t in enumerate(times) if t.time() <= end_time),
        default=None,
    )
    if idx is None:
        raise RuntimeError("No timing points visible")

    ax.text(
        times[idx],
        dist[idx] + offset,
        headcode,
        fontsize=10,
        fontweight="bold",
        color=color,
        ha="right",
        va=va,
        clip_on=True,
        bbox=dict(facecolor="white", edgecolor="none", boxstyle="round,pad=0"),
    )
