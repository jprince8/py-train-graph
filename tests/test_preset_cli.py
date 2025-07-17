import json

import py_train_graph.main as main


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
