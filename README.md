# py‑train‑graph

Plot distance‑time graphs for UK train services using live data from
[RealTimeTrains](https://www.realtimetrains.co.uk/) plus your own
CSV schedules.

![example output](examples/sample_overview.png)

---

## Features

* **One‑command CLI** – grab services, apply a time window and save two PNGs  
* **Custom schedules** – overlay your own timings in bold colours  
* **Disk caching** – repeat runs are instant (uses `requests‑cache` if installed)  
* **Configurable** – reverse routes, filter by direction, limit number plotted  
* **Pure Python ≥ 3.10** – no compiled extensions

---

## Installation

```bash
git clone https://github.com/your‑github/py‑train‑graph.git
cd py‑train‑graph
pip install .
```

Optional extra for faster HTTP caching:

```bash
pip install "py‑train‑graph[dev]"  # also installs requests‑cache
```

---

## Quick start

```bash
py-train-graph routes/london_to_oxford.csv 2025-08-20 03:00 06:00   -l PAD ACTONW HTRWAJN STL   -m 1 --direction up
```

* Saves `graph_<headcodes>_<timestamp>_overview.png` (20 × 10 in, 400 dpi)  
* Saves `graph_<headcodes>_<timestamp>_zoomable.png` (40 × 30 in, 100 dpi)  
* Pops up the interactive plot window (omit `--no-show` to suppress)

---

## CLI reference

```
py-train-graph ROUTE_CSV DATE START END [options]

positional arguments:
  ROUTE_CSV             CSV mapping Location→Distance (mi)
  DATE                  YYYY-MM-DD
  START END             window times HH:MM

optional arguments:
  -l, --locations       list of GB‑NR location codes (required)
  -m, --margin-hours    extend window before/after (hours, default 0)
  -s, --spreadsheet     custom CSV schedule (may repeat)
  -d, --direction       up | down
  -n, --limit           max RTT services plotted
  --reverse-route       plot distances negative
  --no-show             save images only, no GUI
  -v, --verbose         increase logging (-v, -vv)
```

---

## Custom schedules

Create a CSV with at least these columns:

| Location | Arr       | Dep       |
|----------|-----------|-----------|
| PAD[London Paddington] | 00:15:00 | 00:17:00 |
| ACTONW (Acton West)   | 00:25:30 | 00:26:00 |
| ...      | …         | …         |

Times **must** be `HH:MM:SS`.  Use the `-s` flag to include one or more files.

---

## Contributing

1. Fork the repo and create your branch: `git checkout -b feature/foo`
2. Run `ruff --fix` and `black .` before committing
3. Add tests (`pytest`) for new behaviour
4. Open a pull request 🎉

---

## Licence

MIT © Jonathan Prince, 2025
