from render import render_day


def test_render_day_writes_into_per_day_folder(tmp_path):
    data = {
        "date": "2026-08-07",
        "facts": [{"year": 1926, "text": "Das Planetarium Jena wird eröffnet."}],
    }
    render_day(data, tmp_path)

    day_dir = tmp_path / "07"
    assert (day_dir / "01.png").exists()
    caption = (day_dir / "caption.txt").read_text(encoding="utf-8")
    assert "1926" in caption
    assert "Planetarium Jena" in caption
