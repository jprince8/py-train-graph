# py_train_graph/parse.py
"""
Parsing utilities for RealTimeTrains HTML pages and user‑supplied CSV schedules.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from . import utils

__all__ = [
    "fetch_service_links",
    "fetch_service_metadata",
    "parse_service_page",
    "parse_manual_csv",
]

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------#
# RTT helpers                                                                #
# ---------------------------------------------------------------------------#

_SERVICE_LINK_CSS = "a.service"
_LOCATION_WRAPPER_CSS = "div.location.call, div.location.pass"
_WTT_TIME_CSS = "div.wtt"
_NAME_CSS = "div.location > a.name"
_ARR_CSS = "div.arr"
_DEP_CSS = "div.dep"
_TOC_OPERATOR_CSS = "div.toc.h3 > div"
_DEPARTURE_DATE_CSS = "div.header + small"
_TOC_OPERATOR_CSS = "div.toc.h3 > div"
_BUS_ICON_CSS = "div.header span.glyphicons-bus"


def fetch_service_links(html: str) -> list[str]:
    """
    Extract the detailed *service URLs* from a RealTimeTrains search result page.

    Parameters
    ----------
    html
        HTML text of the search results page.

    Returns
    -------
    list[str]
        Absolute URLs (prefixed with ``https://``).
    """
    soup = BeautifulSoup(html, "html.parser")
    links = [
        "https://www.realtimetrains.co.uk" + a["href"]
        for a in soup.select(_SERVICE_LINK_CSS)
    ]
    _LOG.debug("Found %d service links", len(links))
    return links


def fetch_service_metadata(html: str) -> tuple[date, str, str, bool]:
    """
    Extract departure date, headcode, and operator from a RealTimeTrains service detail page.

    Parameters
    ----------
    html : str
        HTML text of the service detail page.

    Returns
    -------
    tuple[date, str, str, bool]
        - Parsed departure date.
        - Uppercase headcode string.
        - Operator name.
        - This is a bus.

    Raises
    ------
    ValueError
        If required elements are missing or the operator is in IGNORE_OPERATORS.
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Bus detection ---
    is_bus = bool(soup.select_one(_BUS_ICON_CSS))

    # --- Departure date ---
    tag = soup.select_one(_DEPARTURE_DATE_CSS)
    if not tag:
        raise ValueError("No departure date element found")
    raw = tag.get_text(strip=True)
    _LOG.debug("Raw departure text: %r", raw)
    if re.search(r"\btoday\b", raw, re.IGNORECASE):
        dep_date = date.today()
    else:
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})", raw)
        if not m:
            raise ValueError(f"Unable to parse departure date from {raw!r}")
        day, month_str, year = m.groups()
        dep_date = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y").date()

    # --- Headcode ---
    title = soup.title.string if soup.title else ""
    try:
        headcode = title.split("|")[1].strip().split()[0]
    except Exception:
        raise ValueError("Headcode not found in title")

    # --- Operator ---
    op_tag = soup.select_one(_TOC_OPERATOR_CSS)
    operator = op_tag.get_text(strip=True) if op_tag else "Other"

    return dep_date, headcode, operator, is_bus


def parse_service_page(html: str, distance_map: pd.Series, start_date: date) -> pd.DataFrame:
    """
    Parse a *single* RealTimeTrains service detail page into a DataFrame.

    Only rows whose ``Location`` is present in *distance_map* are kept.

    Returns
    -------
    pd.DataFrame
        Columns: ``Location``, ``Arr`` (Timestamp), ``Dep`` (Timestamp), ``Distance``.
    """
    soup = BeautifulSoup(html, "html.parser")

    rows: list[tuple[str, str | None, str | None]] = []
    for wrap in soup.select(_LOCATION_WRAPPER_CSS):
        name_tag = wrap.select_one(_NAME_CSS)
        if name_tag is None:
            continue

        text = name_tag.get_text(strip=True)
        loc = re.sub(r"\[.*?\]", "", text).strip()

        wtt = wrap.select_one(_WTT_TIME_CSS)
        arr_txt = dep_txt = None
        if wtt:
            arr_tag = wtt.select_one(_ARR_CSS)
            dep_tag = wtt.select_one(_DEP_CSS)
            if arr_tag and arr_tag.get_text(strip=True) != "pass":
                arr_txt = arr_tag.get_text(strip=True)
            if dep_tag and dep_tag.get_text(strip=True):
                dep_txt = dep_tag.get_text(strip=True)

        rows.append((loc, arr_txt, dep_txt))

    df = pd.DataFrame(rows, columns=["Location", "Arr", "Dep"])

    df["Arr"] = df["Arr"].apply(utils.parse_hhmm_half)
    df["Dep"] = df["Dep"].apply(utils.parse_hhmm_half)

    # 1. Shift any arrivals or departures before the first departure forward by one day
    first_dep = df["Dep"].iloc[0]
    for col in ["Arr", "Dep"]:
        mask = df[col] < first_dep
        df.loc[mask, col] += pd.Timedelta(days=1)

    # 2. Compute how many days to shift so that the first departure’s date == start_date
    first_dep_date = df["Dep"].dt.normalize().iloc[0]
    offset_days = (pd.to_datetime(start_date) - first_dep_date).days

    # 3. Apply that shift to all timestamps
    for col in ["Arr", "Dep"]:
        df[col] = df[col] + pd.Timedelta(days=offset_days)

    df = df[df["Location"].isin(distance_map.index)]

    if df["Location"].nunique() < 2:
        return pd.DataFrame()

    df["Distance"] = df["Location"].map(distance_map["Distance (mi)"])

    return df


# ---------------------------------------------------------------------------#
# Manual CSV parser                                                          #
# ---------------------------------------------------------------------------#


def _resolve_location(target: str, known_locations: pd.Index) -> str | None:
    """
    Return the first known location matching *target*.
    Any '[…]' segments already removed from both strings before here.
    """
    return target if target in known_locations else None


def parse_manual_csv(path: str | Path, distance_map: pd.Series, date_str: str) -> pd.DataFrame:
    """
    Parse a custom schedule CSV created by the user.

    The CSV *must* contain the columns ``Location``, ``Arr``, ``Dep``.
    ``Arr`` and ``Dep`` are parsed as ``HH:MM:SS`` times.

    The function returns a *long‑form* DataFrame with one row per timestamp
    (arrival or departure) inside the file.

    Returns
    -------
    pd.DataFrame
        Columns: ``Time`` (Timestamp) and ``Distance`` (float),
        sorted by time ascending.
    """
    df = pd.read_csv(path)

    required = {"Location", "Arr", "Dep"}
    if not required.issubset(df.columns):
        raise ValueError(f"{os.path.basename(path)} missing columns {required}")

    df = df[["Location", "Arr", "Dep"]].copy()

    # strip out any “[…]” and surrounding whitespace from Location
    df["Location"] = df["Location"].apply(lambda name: re.sub(r"\[.*?\]", "", name).strip())

    # start_date is a datetime.date, e.g. from fetch_service_metadata
    base_ts = pd.Timestamp(date_str)  # midnight on your service date

    # turn “HH:MM:SS” into a timedelta and add the base date in one go
    df["Arr"] = pd.to_timedelta(df["Arr"]) + base_ts
    df["Dep"] = pd.to_timedelta(df["Dep"]) + base_ts

    df["Location"] = df["Location"].apply(
        lambda x: _resolve_location(str(x), distance_map.index)
    )
    df = df[df["Location"].notna()]

    if df.empty:
        raise ValueError(f"{os.path.basename(path)} contains no recognised locations")

    # then map
    df["Distance"] = df["Location"].map(distance_map["Distance (mi)"])

    times: list[pd.Timestamp] = []
    dist: list[float] = []

    for _, row in df.iterrows():
        for tm in (row["Arr"], row["Dep"]):
            if pd.notna(tm):
                times.append(tm)
                dist.append(row["Distance"])

    return (
        pd.DataFrame({"Time": times, "Distance": dist})
        .sort_values("Time")
        .reset_index(drop=True)
    )
