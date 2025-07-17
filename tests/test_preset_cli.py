import json
import time
from pathlib import Path

import py_train_graph.main as main
import py_train_graph.config as config


def test_preset_calls_plot(monkeypatch, tmp_path):
    preset = {
        "route_csv": "routes/london_to_oxford.csv",
        "date": "2025-08-20",
        "start_time": "20:30",
        "end_time": "22:00",
        "locations": ["PAD", "ACTONW"],
        "margin_hours": 0,
        "direction": "down",
        "always_include": [],
        "custom_schedules": ["custom_schedule_example.csv"],
        "limit": 10,
        "reverse_route": None,
        "show_plot": False,
        "same_custom_colour": True,
    }
    preset_path = tmp_path / "preset.json"
    preset_path.write_text(json.dumps(preset), encoding="utf-8")

    called = {}

    def fake_plot_services(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        main, "plot", type("obj", (), {"plot_services": fake_plot_services})
    )
    main.main(["--preset", str(preset_path)])

    assert called["same_custom_colour"] is True
    assert called["limit"] == 10
    assert called["show_plot"] is False


def test_example_preset_loads():
    path = Path("presets/example_preset.json")
    data = main._load_preset(path)
    assert data["locations"][-1] == "DID"


def test_example_preset_cli(monkeypatch):
    called = {}

    def fake_plot_services(**kwargs):
        called.update(kwargs)

    orig_loader = main._load_preset

    def patched_loader(path: Path):
        data = orig_loader(path)
        data["limit"] = 10
        data["show_plot"] = False
        return data

    monkeypatch.setattr(main, "_load_preset", patched_loader)
    monkeypatch.setattr(
        main, "plot", type("obj", (), {"plot_services": fake_plot_services})
    )

    main.main(["--preset", "example_preset"])

    assert called["limit"] == 10
    assert called["show_plot"] is False


def test_example_preset_real_run(monkeypatch):
    out = Path("outputs/test_run")
    monkeypatch.setattr(config, "OUTPUT_DIR", out, raising=False)
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    main.main(["--preset", "example_preset", "-n", "10", "--no-show"])
    duration = time.perf_counter() - start
    assert duration >= 5


