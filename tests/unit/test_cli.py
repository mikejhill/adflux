import json

from adflux.cli import main


def test_to_adf_and_back(tmp_path, capsys):
    md = tmp_path / "in.md"
    md.write_text("# Hi\n\n::toc{maxLevel=2}\n", encoding="utf-8")
    out = tmp_path / "out.json"
    assert main(["to-adf", str(md), "-p", "confluence", "-o", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["content"][1]["attrs"]["extensionKey"] == "toc"
    assert main(["to-md", str(out), "-p", "confluence"]) == 0
    assert capsys.readouterr().out == "# Hi\n\n::toc{maxLevel=2}\n"


def test_validate(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"type":"doc","version":1,"content":[{"type":"nope"}]}', encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    assert "nope" in capsys.readouterr().err
    good = tmp_path / "good.md"
    good.write_text("text", encoding="utf-8")
    assert main(["validate", str(good)]) == 0


def test_errors_and_warnings(tmp_path, capsys):
    md = tmp_path / "x.md"
    md.write_text("::nope", encoding="utf-8")
    assert main(["to-adf", str(md), "-p", "jira"]) == 1
    assert "unknown directive" in capsys.readouterr().err


def test_lookups(capsys):
    assert main(["macros", "toc"]) == 0
    assert json.loads(capsys.readouterr().out)["markdown"].startswith("::toc")
    assert main(["macros", "nope-nope"]) == 1
    assert main(["emoji", "tick", "-p", "confluence"]) == 0
    assert ":tick:" in capsys.readouterr().out
    assert main(["syntax"]) == 0
    assert "Directives" in capsys.readouterr().out
