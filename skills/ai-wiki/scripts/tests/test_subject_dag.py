"""subject_dag: validation + render contract."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import subject_dag  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    (tmp_path / "narratives").mkdir()
    (tmp_path / "maps").mkdir()
    (tmp_path / "narratives" / "ch1.md").write_text("# ch1", encoding="utf-8")
    return tmp_path


def _dag() -> dict:
    return {
        "slug": "demo-dag",
        "title": "demo",
        "regions": {"a": "領域A", "b": "領域B"},
        "nodes": [
            {"id": "X", "layer": 0, "col": 1.0, "region": "a", "title": "X",
             "desc": "d", "trees": [{"slug": "ch1", "label": "ch1"}]},
            {"id": "Y", "layer": 1, "col": 1.0, "region": "b", "title": "Y", "desc": "d"},
        ],
        "edges": [{"from": "X", "to": "Y", "kind": "flow"}],
    }


def test_validate_ok(tmp_path):
    v = _vault(tmp_path)
    r = subject_dag.validate(_dag(), v)
    assert r["ok"] and not r["errors"] and not r["warnings"]
    assert r["node_count"] == 2 and r["edge_count"] == 1


def test_validate_catches_dangling_edge(tmp_path):
    d = _dag()
    d["edges"].append({"from": "X", "to": "Z", "kind": "flow"})
    r = subject_dag.validate(d, _vault(tmp_path))
    assert not r["ok"]
    assert any("Z" in e for e in r["errors"])


def test_validate_catches_bad_kind_and_region(tmp_path):
    d = _dag()
    d["edges"][0]["kind"] = "wobble"
    d["nodes"][0]["region"] = "ghost"
    r = subject_dag.validate(d, _vault(tmp_path))
    assert not r["ok"]
    assert any("wobble" in e for e in r["errors"])
    assert any("ghost" in e for e in r["errors"])


def test_validate_warns_missing_tree(tmp_path):
    d = _dag()
    d["nodes"][0]["trees"] = [{"slug": "nope"}]
    r = subject_dag.validate(d, _vault(tmp_path))
    assert r["ok"]  # missing tree is a warning, not an error
    assert any("nope" in w for w in r["warnings"])


def test_render_roundtrip(tmp_path):
    v = _vault(tmp_path)
    (v / "maps" / "demo-dag.json").write_text(
        json.dumps(_dag(), ensure_ascii=False), encoding="utf-8")
    res = subject_dag.render(v, "demo-dag")
    assert res["ok"]
    html = (v / "maps" / "demo-dag.html").read_text(encoding="utf-8")
    assert "const DAG=" in html and "function sel" in html
    assert "demo" in html and "領域A" in html


def test_render_refuses_invalid(tmp_path):
    v = _vault(tmp_path)
    d = _dag()
    d["edges"][0]["to"] = "Z"
    (v / "maps" / "demo-dag.json").write_text(
        json.dumps(d, ensure_ascii=False), encoding="utf-8")
    res = subject_dag.render(v, "demo-dag")
    assert not res["ok"] and "report" in res
