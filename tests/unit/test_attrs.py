import pytest

from adflux.errors import MarkdownError
from adflux.markdown.attrs import format_attrs, parse_attrs, quote


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{}", {}),
        ("{a=1}", {"a": "1"}),
        ("{a=1 b=two}", {"a": "1", "b": "two"}),
        ('{title="Hello world"}', {"title": "Hello world"}),
        ("{title='it''s'}", None),
        (r'{t="say \"hi\""}', {"t": 'say "hi"'}),
        (r"{t='a\nb'}", {"t": "a\nb"}),
        ("{flag}", {"flag": "true"}),
        ("{  a=1   flag  }", {"a": "1", "flag": "true"}),
        ("{adf.key=toc ns:x=1}", {"adf.key": "toc", "ns:x": "1"}),
    ],
)
def test_parse(source, expected):
    if expected is None:
        with pytest.raises(MarkdownError):
            parse_attrs(source)
        return
    attrs, end = parse_attrs(source)
    assert attrs == expected
    assert end == len(source)


@pytest.mark.parametrize("source", ["{", "{a=", "{a=1", '{a="x}', "{1=2}", "x"])
def test_parse_errors(source):
    with pytest.raises(MarkdownError):
        parse_attrs(source)


def test_parse_offset():
    attrs, end = parse_attrs("::toc{maxLevel=3} tail", 5)
    assert attrs == {"maxLevel": "3"}
    assert end == 17


@pytest.mark.parametrize(
    "value", ["", "plain", "with space", 'q"uote', "back\\slash", "new\nline", "{x}", "a=b", "#ff0000", "😀"]
)
def test_quote_roundtrip(value):
    attrs, _ = parse_attrs(format_attrs({"k": value}))
    assert attrs == {"k": value}


def test_quote_bare_when_safe():
    assert quote("abc-1.2") == "abc-1.2"
    assert quote("a b") == '"a b"'
    assert format_attrs({}) == ""
