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


def test_save_selection_prefers_text_de_over_original(tmp_path):
    candidates = [{"id": "a", "year": 1941, "text": "Germany invades the Soviet Union.", "text_de": "Deutschland fällt in die Sowjetunion ein."}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["a"])
    out = tmp_path / "2026-07" / "17.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["facts"][0]["text"] == "Deutschland fällt in die Sowjetunion ein."


def test_save_selection_keeps_original_text_when_no_translation(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x", "text_de": None}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["a"])
    out = tmp_path / "2026-07" / "17.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["facts"][0]["text"] == "x"


def test_save_selection_rejects_more_than_nine(tmp_path):
    candidates = [{"id": str(i)} for i in range(10)]
    try:
        curate_logic.save_selection(tmp_path, "2026-07-17", candidates, [str(i) for i in range(10)])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass


def test_save_selection_rejects_empty_selection(tmp_path):
    candidates = [{"id": "1"}]
    try:
        curate_logic.save_selection(tmp_path, "2026-07-17", candidates, [])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass


def test_load_selected_ids_missing_returns_empty(tmp_path):
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == []


def test_load_selected_ids_reads_existing_selection(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x"}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["a"])
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == ["a"]


def test_load_candidates_rejects_path_traversal(tmp_path):
    try:
        curate_logic.load_candidates(tmp_path, "a/b")
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass


def test_save_selection_rejects_absolute_reset_date(tmp_path):
    try:
        curate_logic.save_selection(tmp_path, "2026-07/../../etc", [], [])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass

