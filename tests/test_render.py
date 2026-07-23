from pathlib import Path

from render import build_caption, render_day


def test_render_day_writes_one_png_per_fact(tmp_path):
    data = {
        "date": "2026-08-07",
        "facts": [
            {"year": 1926, "text": "Das Planetarium Jena wird eröffnet."},
            {"year": None, "text": "Ein Ereignis ohne bekanntes Jahr."},
            {"year": 1969, "text": "Die Apollo-11-Mission landet als erste bemannte Mission auf dem Mond."},
        ],
    }
    render_day(data, tmp_path)

    day_dir = tmp_path / "07"
    assert (day_dir / "01.png").exists()
    assert (day_dir / "02.png").exists()
    assert (day_dir / "03.png").exists()
    assert not (day_dir / "04.png").exists()

    caption = (day_dir / "caption.txt").read_text(encoding="utf-8")
    assert "1926" in caption
    assert "Planetarium Jena" in caption
    assert "Apollo-11" in caption


def test_render_day_single_fact(tmp_path):
    data = {
        "date": "2026-07-04",
        "facts": [{"year": 1969, "text": "Erste Mondlandung."}],
    }
    render_day(data, tmp_path)

    day_dir = tmp_path / "04"
    assert (day_dir / "01.png").exists()
    assert not (day_dir / "02.png").exists()


def test_build_caption_format():
    data = {
        "date": "2026-08-07",
        "facts": [{"year": 1926, "text": "Das Planetarium Jena wird eröffnet."}],
    }
    caption = build_caption(data)
    assert caption.startswith("📅 7. August 2026")
    assert "• 1926: Das Planetarium Jena wird eröffnet." in caption
    assert caption.endswith("#aufdenTag #geschichte #onthisday #wissen")


def test_build_caption_omits_year_when_missing():
    data = {
        "date": "2026-08-07",
        "facts": [{"year": None, "text": "Ein Ereignis ohne bekanntes Jahr."}],
    }
    caption = build_caption(data)
    assert "• Ein Ereignis ohne bekanntes Jahr." in caption
    assert "None" not in caption


def test_render_day_no_leftover_render_html_in_templates_dir():
    # ponytail: die temporäre Render-HTML wird in templates/ geschrieben (Font-Pfad-Fix,
    # siehe Plan-Kopf) — dieser Test stellt sicher, dass sie danach wieder aufgeräumt wird.
    templates_dir = Path(__file__).parent.parent / "templates"
    before = set(templates_dir.glob("*.html"))

    data = {"date": "2026-08-07", "facts": [{"year": 1926, "text": "Test."}]}
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        render_day(data, Path(tmp))

    after = set(templates_dir.glob("*.html"))
    assert before == after
