# py_train_graph/__init__.py
"""
Top‑level package for **py‑train‑graph**.

Public re‑exports
-----------------
`plot_services`
    Convenience import so users can:

    >>> from py_train_graph import plot_services
"""

from __future__ import annotations

__all__ = ["plot_services", "__version__"]

__version__: str = "0.1.0"

from .plot import plot_services  # noqa: E402  (import after defining __all__)
