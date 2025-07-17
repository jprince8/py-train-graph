import pandas as pd
import pytest

import py_train_graph.main as main
import py_train_graph.utils as utils
import py_train_graph.parse as parse


def test_resolve_path(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text("{}", encoding="utf-8")

    # existing absolute path
    assert main._resolve_path(str(f), tmp_path, "json") == f

    # by name within target directory
    assert main._resolve_path("foo", tmp_path, "json") == f

    # path under subdirectory
    sub = tmp_path / "sub"
    sub.mkdir()
    f2 = sub / "bar.json"
    f2.write_text("{}", encoding="utf-8")
    assert main._resolve_path(str(sub / "bar"), tmp_path, "json") == f2

    with pytest.raises(FileNotFoundError):
        main._resolve_path("missing", tmp_path, "json")


def test_parse_manual_csv_errors(tmp_path):
    distance_map = pd.DataFrame(
        {"Distance (mi)": [0]}, index=pd.Index(["A"], name="Location")
    )

    bad = tmp_path / "bad.csv"
    bad.write_text("Location,Arr\nA,12:00:00\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse.parse_manual_csv(bad, distance_map, "2025-01-01")

    unknown = tmp_path / "unknown.csv"
    unknown.write_text("Location,Arr,Dep\nX,12:00:00,12:01:00\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse.parse_manual_csv(unknown, distance_map, "2025-01-01")


def test_generate_rtt_urls_cross_midnight():
    urls = utils.generate_rtt_urls(
        ["PAD"], "2025-01-02", "01:00", "02:00", margin_hours=2
    )
    assert len(urls) == 2
    assert "2025-01-01" in urls[0]
    assert "2300" in urls[0]
    assert "2025-01-02" in urls[1]
    assert urls[1].endswith("02:00".replace(":", "")) or "0200" in urls[1]
