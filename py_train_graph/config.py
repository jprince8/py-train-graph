# config.py
"""
Central configuration for the *py-train-graph* project.

All project‑wide constants live here so they can be reused
across modules and, if desired, overridden by the user at runtime.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------#
# Directories (created on import)                                            #
# ---------------------------------------------------------------------------#

CACHE_DIR: Path = Path("cache")
ROUTE_DIR: Path = Path("routes")
CUSTOM_SCHEDULE_DIR: Path = Path("custom_schedules")
OUTPUT_DIR: Path = Path("outputs")

for _dir in (CACHE_DIR, ROUTE_DIR, CUSTOM_SCHEDULE_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------#
# Plotting settings                                                          #
# ---------------------------------------------------------------------------#

MID_BLUE: str = "#3838C8"
DARK_GREY: str = "#4F4F4F"

ZOOMABLE_FIGSIZE: tuple[int, int] = (40, 30)
OVERVIEW_FIGSIZE: tuple[int, int] = (20, 10)

ZOOMABLE_DPI: int = 100
OVERVIEW_DPI: int = 400

# ---------------------------------------------------------------------------#
# Behaviour flags                                                            #
# ---------------------------------------------------------------------------#

REVERSE_ROUTE: bool = True
USE_CUSTOM: bool = True
SHOW_PLOT: bool = True

# ---------------------------------------------------------------------------#
# External service URLs                                                      #
# ---------------------------------------------------------------------------#

RTT_DETAILED_URL: str = (
    "https://www.realtimetrains.co.uk/search/detailed/gb-nr:{loc}/{date}/{start}-{end}"
)

# ---------------------------------------------------------------------------#
# Operator colours (extendable by users)                                     #
# ---------------------------------------------------------------------------#

OPERATOR_COLOURS: dict[str, str] = {
    "Great Western Railway": "#0b4d3b",
    "Elizabeth Line": "#694ED6",
    "Heathrow Express": "#5e5e5e",
    "CrossCountry": "#aa007f",
    'South Western Railway': '#00557f',
    "Other": "#8B4513",
}

# ---------------------------------------------------------------------------#
# Operators to ignore                                                        #
# ---------------------------------------------------------------------------#

IGNORE_OPERATORS: list[str] = [
    "RA1"
]
