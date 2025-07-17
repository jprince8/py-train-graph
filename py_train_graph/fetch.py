# py_train_graph/fetch.py
"""
Network layer with transparent on‑disk caching.

If *requests‑cache* is available, it is used automatically (SQLite backend
inside ``config.CACHE_DIR``).  Otherwise a lightweight manual cache based on
MD5‑hashed filenames is used.  Either way, callers simply call
:pyfunc:`get_html` and receive HTML text.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from . import config, utils

__all__ = ["get_html"]

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------#
# requests‑cache integration (optional)                                      #
# ---------------------------------------------------------------------------#

_REQUESTS_CACHE_OK: bool
_SESSION: requests.Session

try:
    import requests_cache  # type: ignore

    cache_path = config.CACHE_DIR / "http_cache.sqlite"
    _SESSION = requests_cache.CachedSession(  # pragma: no cover
        cache_name=str(cache_path),
        backend="sqlite",
        expire_after=None,  # never expire; remote pages are mostly static
    )
    _REQUESTS_CACHE_OK = True
    _LOG.debug("Using requests‑cache at %s", cache_path)
except ModuleNotFoundError:  # pragma: no cover
    _SESSION = requests.Session()
    _REQUESTS_CACHE_OK = False
    _LOG.debug("requests‑cache not available; falling back to manual cache")


# ---------------------------------------------------------------------------#
# Manual disk cache fallback                                                 #
# ---------------------------------------------------------------------------#


def _manual_cache_path(url: str) -> Path:
    """Return the filesystem path for a cached copy of *url*."""
    return config.CACHE_DIR / utils.url_to_filename(url)


def _get_manual_cached(url: str) -> str | None:
    """Return cached HTML text if present, else *None*."""
    path = _manual_cache_path(url)
    if path.exists():
        _LOG.debug("Manual cache hit for %s", url)
        return path.read_text(encoding="utf‑8")
    return None


def _store_manual_cache(url: str, text: str) -> None:
    """Persist HTML text for *url* to disk."""
    path = _manual_cache_path(url)
    path.write_text(text, encoding="utf‑8")
    _LOG.debug("Stored manual cache for %s", url)


# ---------------------------------------------------------------------------#
# Public API                                                                 #
# ---------------------------------------------------------------------------#


def get_html(url: str, *, force_refresh: bool = False) -> str:
    """
    Fetch *url* and return its HTML content as a Unicode string.

    The first call is cached; subsequent calls are served from cache unless
    *force_refresh* is True.

    Raises
    ------
    requests.HTTPError
        If the HTTP status is not 200 OK.
    """
    if not force_refresh and not _REQUESTS_CACHE_OK:
        cached = _get_manual_cached(url)
        if cached is not None:
            return cached

    # Either no cache hit, or user requested fresh, or using requests‑cache
    resp = _SESSION.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text

    if not _REQUESTS_CACHE_OK:
        _store_manual_cache(url, html)

    return html
