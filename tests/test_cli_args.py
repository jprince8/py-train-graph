import py_train_graph.main as main


def test_cli_calls_plot(monkeypatch):
    called = {}

    def fake_plot_services(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        main, "plot", type("obj", (), {"plot_services": fake_plot_services})
    )

    main.main(
        [
            "routes/london_to_oxford.csv",
            "2025-08-20",
            "20:30",
            "22:00",
            "-l",
            "PAD",
            "ACTONW",
            "--no-show",
            "-n",
            "5",
        ]
    )

    assert called["limit"] == 5
    assert called["show_plot"] is False
    assert called["locations"] == ["PAD", "ACTONW"]
