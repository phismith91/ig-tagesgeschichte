import json

import curate_logic


def _write_candidates(base, date_str, candidates):
    path = base / date_str[:7] / f"{date_str[-2:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": date_str, "candidates": candidates}), encoding="utf-8")


def test_load_candidates_missing_returns_empty(tmp_path):
    assert curate_logic.load_candidates(tmp_path, "2026-07-17") == []


def test_load_candidates_reads_file(tmp_path):
    _write_candidates(tmp_path, "2026-07-17", [{"id": "wp-0"}])
    assert curate_logic.load_candidates(tmp_path, "2026-07-17") == [{"id": "wp-0"}]


def test_resolve_selection_preserves_order():
    candidates = [{"id": "a", "v": 1}, {"id": "b", "v": 2}, {"id": "c", "v": 3}]
    result = curate_logic.resolve_selection(candidates, ["c", "a"])
    assert [r["id"] for r in result] == ["c", "a"]


def test_resolve_selection_ignores_unknown_ids():
    candidates = [{"id": "a", "v": 1}]
    result = curate_logic.resolve_selection(candidates, ["a", "ghost"])
    assert [r["id"] for r in result] == ["a"]


def test_save_selection_writes_facts(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x"}, {"id": "b", "year": 1999, "text": "y"}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["b", "a"])
    out = tmp_path / "2026-07" / "17.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["date"] == "2026-07-17"
    assert [f["id"] for f in data["facts"]] == ["b", "a"]


def test_save_selection_rejects_more_than_nine(tmp_path):
    candidates = [{"id": str(i)} for i in range(10)]
    try:
        curate_logic.save_selection(tmp_path, "2026-07-17", candidates, [str(i) for i in range(10)])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass


def test_load_selected_ids_missing_returns_empty(tmp_path):
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == []


def test_load_selected_ids_reads_existing_selection(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x"}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["a"])
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == ["a"]


def test_next_unfinished_day_skips_curated(tmp_path):
    candidates_dir = tmp_path / "candidates"
    curate_dir = tmp_path / "curate"
    _write_candidates(candidates_dir, "2026-07-01", [{"id": "a"}])
    _write_candidates(candidates_dir, "2026-07-02", [{"id": "b"}])
    curate_logic.save_selection(curate_dir, "2026-07-01", [{"id": "a", "year": 1, "text": "x"}], ["a"])
    assert curate_logic.next_unfinished_day(candidates_dir, curate_dir, "2026-07") == "2026-07-02"


def test_next_unfinished_day_all_done_returns_first(tmp_path):
    candidates_dir = tmp_path / "candidates"
    curate_dir = tmp_path / "curate"
    _write_candidates(candidates_dir, "2026-07-01", [{"id": "a"}])
    curate_logic.save_selection(curate_dir, "2026-07-01", [{"id": "a", "year": 1, "text": "x"}], ["a"])
    assert curate_logic.next_unfinished_day(candidates_dir, curate_dir, "2026-07") == "2026-07-01"


def test_next_unfinished_day_no_candidates_returns_none(tmp_path):
    assert curate_logic.next_unfinished_day(tmp_path / "candidates", tmp_path / "curate", "2026-07") is None
