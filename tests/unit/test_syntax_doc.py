"""Every example in the packaged syntax guide converts, validates and round-trips."""

import re
from importlib import resources

import pytest

from adflux import to_adf, to_markdown, validate
from adflux.adf.normalize import canonical

GUIDE = resources.files("adflux").joinpath("syntax.md").read_text(encoding="utf-8")
BLOCKS = list(re.findall(r"^```\n(.*?)^```$", GUIDE, flags=re.S | re.M))


@pytest.mark.parametrize("source", BLOCKS)
def test_guide_blocks(source):
    doc = to_adf(source, "confluence")
    validate(doc)
    assert canonical(to_adf(to_markdown(doc, "confluence"), "confluence")) == canonical(doc)


@pytest.mark.parametrize(
    "source",
    [
        "**bold** *italic* ~~strike~~ `code`",
        "<u>under</u> <sub>2</sub> <sup>2</sup>",
        '[text](https://x.example "title")',
        ":span[text]{color=#ff5630 background=#fffae6}",
        ":smile: :check_mark: :status[DONE]{color=green} :date[2025-01-31] :mention[@Ada]{id=abc}",
        ":::paragraph{align=center}\nx\n:::",
        ":::heading{level=2 indent=1}\nx\n:::",
        "::rule",
        'x :placeholder{text="Type here"}',
        ":tick: :information:",
        '```adf\n{"type": "rule"}\n```',
    ],
)
def test_guide_snippets(source):
    validate(to_adf(source, "confluence"))
