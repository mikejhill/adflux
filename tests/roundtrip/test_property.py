"""Property: any schema-valid ADF document survives ADF -> Markdown -> ADF."""

from hypothesis import given, settings

from adflux import to_adf, to_markdown
from adflux.adf import validate
from adflux.adf.model import load
from adflux.adf.normalize import canonical, expel_whitespace, normalize
from tests.strategies import documents


def _canon(doc):
    return canonical(expel_whitespace(normalize(load(doc))))


@settings(max_examples=15)
@given(documents)
def test_strategy_builds_schema_valid_adf(doc):
    validate(load(doc))  # full JSON Schema pass (slow), so few examples


@given(documents)
def test_adf_markdown_adf(doc):
    validate(load(doc), schema=False)
    for profile in ("generic", "confluence", "jira"):
        markdown = to_markdown(doc, profile)
        back = to_adf(markdown, profile)
        assert _canon(back) == _canon(doc), markdown
