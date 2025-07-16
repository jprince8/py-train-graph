import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import requests
import os
from bs4 import BeautifulSoup
import matplotlib.dates as mdates
from datetime import datetime as _dt
from datetime import timedelta
from tqdm import tqdm
import hashlib
from pathlib import Path
from tabulate import tabulate

# ---- customisation ---------------------------------------------------------
MID_BLUE = '#3838C8'
DARK_GREY = '#4F4F4F'
ZOOMABLE_FIGSIZE = (40, 30)
OVERVIEW_FIGSIZE = (20, 10)
ZOOMABLE_DPI = 100
OVERVIEW_DPI = 400

# ---- configuration ---------------------------------------------------------
REVERSE_ROUTE = True
USE_CUSTOM = True
SHOW_PLOT = True
SAVE_WITH_DATE = False

# ---- directories -----------------------------------------------------------
CACHE_DIR = Path('cache')
ROUTE_DIR = Path('routes')
CUSTOM_SCHEDULE_DIR = Path('custom schedules')
OUTPUT_DIR = Path('outputs')
os.makedirs(CACHE_DIR, exist_ok=True)

# ---- helpers ---------------------------------------------------------------

def _parse_hhmm_half(text: str):
    """Convert HHMM or HHMM½ to pandas Timestamp or None."""
    if pd.isna(text):
        return None
    text = str(text).strip().replace('½', '.5')
    try:
        if '.' in text:
            return pd.to_datetime(text, format='%H%M.%f')
        return pd.to_datetime(text, format='%H%M')
    except Exception:
        return None


def _label_last_point(ax, end_time, times, dist, headcode, color, direction):
    """Annotate last plotted point within current x‑axis limits."""
    if not times:
        return
    if REVERSE_ROUTE:
        if direction == 'up':
            va = "bottom"
            offset = 0.2
        else:
            va = "top"
            offset = -0.2
    else:
        if direction == 'up':
            va = "top"
            offset = -0.2
        else:
            va = "bottom"
            offset = 0.2
    idx = max((i for i, t in enumerate(times) if t.time() < end_time), default=None)
    if idx is not None:
        ax.text(times[idx], dist[idx] + offset, headcode,
                fontsize=10, fontweight='bold', color=color,
                ha='right', va=va, clip_on=True,
                bbox=dict(facecolor='white', edgecolor='none', boxstyle='round,pad=0'))


def url_to_filename(url):
    return hashlib.md5(url.encode()).hexdigest() + '.html'


def get_cached_html(url):
    cache_path = os.path.join(CACHE_DIR, url_to_filename(url))
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()
    html = requests.get(url).text
    with open(cache_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return html

# ---- background ------------------------------------------------------------

def plot_distances_background(distance_map, ax):
    distances = distance_map.values
    locations = distance_map.index
    ax.margins(x=0)
    tick_locs, tick_labels = [], []
    for label, d in zip(locations, distances):
        if '[' in label:
            ax.hlines(d, 0, 1, linestyles='dashed', color=MID_BLUE, alpha=0.4,
                      transform=ax.get_yaxis_transform())
            tick_locs.append(d)
            tick_labels.append(label)
        else:
            ax.hlines(d, 0, 1, linestyles='dashed', color=DARK_GREY, alpha=0.2,
                      transform=ax.get_yaxis_transform())
    ax.set_yticks(tick_locs)
    ax.set_yticklabels(tick_labels)
    for lbl in ax.get_yticklabels():
        lbl.set_color(MID_BLUE)

# ---- distance map ----------------------------------------------------------

def plot_distances(csv_path):
    df = pd.read_csv(csv_path)
    distances = df.set_index('Location')['Distance (mi)']
    if REVERSE_ROUTE:
        distances = -distances
    return distances

# ---- RTT page parsing ------------------------------------------------------

def generate_rtt_urls(locations: list[str], date: str, start_time: str, end_time: str, margin_hours: int) -> list[str]:
    """Generate RTT URLs for a list of location codes and time window with margin."""
    fmt = "%H:%M"
    start_dt = _dt.strptime(start_time, fmt) - timedelta(hours=margin_hours)
    end_dt = _dt.strptime(end_time, fmt) + timedelta(hours=margin_hours)

    # Clamp to valid 24h clock range
    start_str = max(start_dt, _dt.strptime("00:00", fmt)).strftime("%H%M")
    end_str = min(end_dt, _dt.strptime("23:59", fmt)).strftime("%H%M")

    return [
        f"https://www.realtimetrains.co.uk/search/detailed/gb-nr:{loc}/{date}/{start_str}-{end_str}"
        for loc in locations
    ]

def fetch_service_links(base_url):
    """
    Returns list of service detail URLs from the main table.
    """
    resp = requests.get(base_url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = soup.select('a.service')
    return ['https://www.realtimetrains.co.uk' + a['href'] for a in links]

def parse_service_page(html: str, distance_map: pd.Series) -> pd.DataFrame:
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for wrap in soup.select('div.location.call, div.location.pass'):
        name_tag = wrap.select_one('div.location > a.name')
        if not name_tag:
            continue
        loc = name_tag.get_text(strip=True)
        wtt = wrap.select_one('div.wtt')
        arr_txt = dep_txt = None
        if wtt:
            arr_tag = wtt.select_one('div.arr'); dep_tag = wtt.select_one('div.dep')
            if arr_tag and arr_tag.get_text(strip=True) != 'pass':
                arr_txt = arr_tag.get_text(strip=True)
            if dep_tag and dep_tag.get_text(strip=True):
                dep_txt = dep_tag.get_text(strip=True)
        rows.append((loc, arr_txt, dep_txt))
    df = pd.DataFrame(rows, columns=['Location','Arr','Dep'])
    df = df[df['Location'].isin(distance_map.index)]
    if df.shape[0] < 2:
        return pd.DataFrame()
    df['Arr'] = df['Arr'].apply(_parse_hhmm_half)
    df['Dep'] = df['Dep'].apply(_parse_hhmm_half)
    df['Distance'] = df['Location'].map(distance_map)
    return df

# ---- manual spreadsheet parsing -------------------------------------------

def parse_manual_csv(path: str, distance_map: pd.Series) -> pd.DataFrame:
    df = pd.read_csv(path)

    required_cols = {'Location', 'Arr', 'Dep'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Expected columns {required_cols}, but got {set(df.columns)}")

    df = df[['Location', 'Arr', 'Dep']].copy()

    # Parse time columns (assumed format hh:mm:ss)
    df['Arr'] = pd.to_datetime(df['Arr'], format='%H:%M:%S', errors='coerce')
    df['Dep'] = pd.to_datetime(df['Dep'], format='%H:%M:%S', errors='coerce')

    # Filter to known locations
    def resolve_location(loc: str, known_locs: pd.Index) -> str | None:
        for known in known_locs:
            if loc in known:
                return known
        return None

    df['Location'] = df['Location'].apply(lambda x: resolve_location(x, distance_map.index))
    df = df[df['Location'].notnull()]

    if df.empty:
        raise ValueError("No valid locations found after filtering with distance_map")

    # Map distances
    df['Distance'] = df['Location'].map(distance_map)

    # Build filtered list
    times, dist = [], []
    for _, row in df.iterrows():
        for tm in (row['Arr'], row['Dep']):
            if pd.notnull(tm):
                times.append(tm)
                dist.append(row['Distance'])

    if len(times) < 2:
        # raise ValueError("Not enough valid time-distance points in the given time window")
        pass

    return pd.DataFrame({'Time': times, 'Distance': dist}).sort_values('Time')


# ---- main plotting ---------------------------------------------------------

def plot_services(
    route_csv: str,
    locations: list[str],
    always_include: list[str],
    date: list[str],
    start_time: str,
    end_time: str,
    margin_hours: int,
    *,
    spreadsheets: list[str] | None = None,
    limit: int | None = None,
    direction: str | None = None,
):
    """Plot RTT services and manual spreadsheets.

    Parameters
    ----------
    route_csv : str  – location → distance mapping
    base_urls : list[str]  – list of RTT detail-page URLs
    start_time, end_time : 'HH:MM' strings indicating window
    spreadsheets : optional list of CSV paths with Location,Time columns
    limit : max number of RTT services to plot (manual files not limited)
    direction : 'up' or 'down' distance monotonic filter
    """
    distance_map = plot_distances(route_csv)
    base_urls = generate_rtt_urls(locations, date, start_time, end_time, margin_hours)
    urls = [url for u in base_urls for url in fetch_service_links(u)]
    start_t = _dt.strptime(start_time,'%H:%M').time()
    end_t   = _dt.strptime(end_time,  '%H:%M').time()

    fig, ax = plt.subplots(figsize=OVERVIEW_FIGSIZE)
    ax.grid(True, axis='x', alpha=0.5)
    plot_distances_background(distance_map, ax)

    plotted = []
    seen_urls = []
    ignore_operators = ["RA1"]
    operator_colours = {
        'Great Western Railway':'#0b4d3b',
        'Elizabeth Line':'#694ED6',
        'Heathrow Express':'#5e5e5e',
        'CrossCountry':'#aa007f',
        'South Western Railway':'#00557f',
        'Other':'#8B4513'
    }
    custom_colors = iter([
        '#ff0000',
        '#ffaa00',
        '#00ff00',
    ])

    # --- plot RTT services --------------------------------------------------
    count = 0
    # for url in urls:
    for url in tqdm(urls):
        if limit and count >= limit:
            break
        if url in seen_urls:
            continue
        seen_urls.append(url)
        html = get_cached_html(url)
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.string if soup.title else ''
        try:
            headcode = title.split('|')[1].strip().split()[0]
        except Exception:
            continue
        if not headcode:
            raise AssertionError(f"Missing headcode: headcode={headcode!r}")
        op_tag = soup.select_one('div.toc.h3 > div')
        operator = op_tag.get_text(strip=True) if op_tag else "Other"
        if operator in ignore_operators:
            continue
        color = operator_colours.get(operator)
        if color is None:
            print(url)
            raise ValueError(f"Unknown operator: {operator} ({headcode})")
        df = parse_service_page(html, distance_map)
        if df.empty:
            continue
        # window filter
        times, dist = [], []
        for _, row in df.iterrows():
            for tm in (row['Arr'], row['Dep']):
                if pd.notnull(tm) and start_t <= tm.time() <= end_t:
                    times.append(tm); dist.append(row['Distance'])
        if not times:
            continue
        if headcode not in always_include:
            if REVERSE_ROUTE:
                if direction=='down' and not all(np.diff(dist)<=0):
                    continue
                if direction=='up' and not all(np.diff(dist)>=0):
                    continue
            else:
                if direction=='up' and not all(np.diff(dist)<=0):
                    continue
                if direction=='down' and not all(np.diff(dist)>=0):
                    continue
        ax.plot(times, dist, marker='o', markersize=3, linestyle='-', color=color, label=headcode)
        _label_last_point(ax, end_t, times, dist, headcode, color, direction)
        plotted.append((headcode, url))
        count += 1
        # print(headcode, operator)

    # --- plot manual spreadsheets ------------------------------------------
    custom_headcodes = []
    if spreadsheets and USE_CUSTOM:
        for path in spreadsheets:
            df = parse_manual_csv(path, distance_map)
            if df.empty:
                continue
            times = df['Time'].tolist(); dist = df['Distance'].tolist()
            times_window = [t for t in times if start_t <= t.time() <= end_t]
            dist_window  = [d for t,d in zip(times,dist) if start_t <= t.time() <= end_t]
            if not times_window:
                continue
            if REVERSE_ROUTE:
                if direction=='down' and not all(np.diff(dist_window)<=0):
                    continue
                if direction=='up' and not all(np.diff(dist_window)>=0):
                    continue
            else:
                if direction=='up' and not all(np.diff(dist_window)<=0):
                    continue
                if direction=='down' and not all(np.diff(dist_window)>=0):
                    continue
            headcode = os.path.splitext(os.path.basename(path))[0]
            color = next(custom_colors)
            ax.plot(times_window, dist_window, marker='o', markersize=4, linestyle='-', linewidth=2,
                    color=color, label=headcode)
            _label_last_point(ax, end_t, times_window, dist_window, headcode, color, direction)
            plotted.append((headcode, path))
            custom_headcodes.append(headcode)
            # print(headcode, "User Added")

    # --- print summary ------------------------------------------------------
    if plotted:
        tbl = pd.DataFrame(plotted, columns=['Headcode','Source'])
        print("Plotted services:")
        print(tabulate(tbl, headers='keys', tablefmt='grid', showindex=False))
        print()

    # set x‑axis to window of first plotted item
    if plotted:
        base_date = sorted([t for line in ax.get_lines() for t in line.get_xdata()])[0].date()
        ax.set_xlim(_dt.combine(base_date,start_t), _dt.combine(base_date,end_t))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    ax.set_xlabel('Time'); ax.set_ylabel('Distance (mi)')
    plt.subplots_adjust(left=0.12,right=0.98,top=0.98,bottom=0.1)

    if SAVE_WITH_DATE:
        timestamp = "_"+_dt.now().strftime("%y%m%d_%H%M")
    else:
        timestamp = ""
    output_path = OUTPUT_DIR / f"graph_{'_'.join(custom_headcodes)}{timestamp}_overview.png"
    plt.savefig(output_path, dpi=OVERVIEW_DPI, bbox_inches="tight")
    print(f"Saved overview image to {output_path}\n")
    # Change figure size and save again
    fig.set_size_inches(ZOOMABLE_FIGSIZE)
    output_path = OUTPUT_DIR / f"graph_{'_'.join(custom_headcodes)}{timestamp}_zoomable.png"
    plt.savefig(output_path, dpi=ZOOMABLE_DPI, bbox_inches="tight")
    print(f"Saved zoomable higher res image to {output_path}\n")
    fig.set_size_inches(OVERVIEW_FIGSIZE)

    if SHOW_PLOT:
        plt.show()


# ---- example --------------------------------------------------------------


locations = ['PAD', 'ACTONW', 'HTRWAJN', 'STL', 'REDGWJN', 'DIDCTNJ', 'RDG']
always_include = ['2H75']
date = '2025-08-20'
route = ROUTE_DIR / 'london_to_oxford.csv'
pre_select = False
# pre_select = "4"


selected = pre_select or input("Enter number(s): ").split(' ')
if "1" in selected:
    plot_services(
        route, locations, always_include,
        date, start_time='00:00', end_time='02:00', margin_hours=1,
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q90.csv'],
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q90.csv', CUSTOM_SCHEDULE_DIR / '3Q90_jp1.csv'],
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q90.csv', CUSTOM_SCHEDULE_DIR / '3Q90_earlier1.csv'],
        spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q80.csv', CUSTOM_SCHEDULE_DIR / '3Q80_jp1.csv'],
        limit=None, direction='up'
    )
if "2" in selected:
    plot_services(
        route, locations, always_include,
        # date, start_time='01:30', end_time='04:00', margin_hours=1,
        date, start_time='01:00', end_time='03:30', margin_hours=1,
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q91.csv'],
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q91.csv', CUSTOM_SCHEDULE_DIR / '3Q91_jp1.csv'],
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q91.csv', CUSTOM_SCHEDULE_DIR / '3Q91_earlier1.csv'],
        spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q81.csv', CUSTOM_SCHEDULE_DIR / '3Q81_jp1.csv'],
        limit=None, direction='down'
    )
if "3" in selected:
    plot_services(
        route, locations, always_include,
        date, start_time='03:00', end_time='06:00', margin_hours=1,
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q92.csv'],
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q92.csv', CUSTOM_SCHEDULE_DIR / '3Q92_jp1.csv'],
        spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q92.csv', CUSTOM_SCHEDULE_DIR / '3Q92_earlier1.csv'],
        limit=None, direction='up'
    )
if "4" in selected:
    plot_services(
        route, locations, always_include,
        date, start_time='05:00', end_time='07:00', margin_hours=1,
        # spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q93.csv'],
        spreadsheets=[CUSTOM_SCHEDULE_DIR / '3Q93.csv', CUSTOM_SCHEDULE_DIR / '3Q93_earlier1.csv'],
        limit=None, direction='down'
    )
