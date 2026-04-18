"""Edge-case tests for content that should NOT be reinterpreted.

Covers:
- Literal ``@`` text that is not an ADF mention.
- ADF-like syntax inside fenced code blocks and inline code.
- HTML comment markers inside code (should remain literal).
"""

from __future__ import annotations

import json

from adflux import convert


# ---------------------------------------------------------------------------
# @ signs in regular text must not become ADF mentions
# ---------------------------------------------------------------------------


def test_at_sign_in_text_survives_md_to_adf():
    """A bare ``@gmail.com`` in prose must stay as plain text in ADF."""
    md = "Use @gmail.com emails for recipients."
    adf = json.loads(convert(md, src="md", dst="adf"))
    content = adf["content"]

    # The paragraph should contain only text nodes, no mentions.
    para = content[0]
    assert para["type"] == "paragraph"
    node_types = {n["type"] for n in para["content"]}
    assert "mention" not in node_types

    # The text must still contain the original @ string.
    texts = " ".join(n.get("text", "") for n in para["content"])
    assert "@gmail.com" in texts


def test_at_sign_roundtrips_through_adf():
    """MD → ADF → MD must preserve bare ``@`` text unchanged."""
    md = "Contact @someone about the issue.\n"
    adf = convert(md, src="md", dst="adf")
    back = convert(adf, src="adf", dst="md")
    assert "@someone" in back


def test_multiple_at_signs_in_paragraph():
    """Several bare ``@`` fragments in one paragraph stay as text."""
    md = "Email @alice and @bob at @example.org.\n"
    adf = json.loads(convert(md, src="md", dst="adf"))
    para = adf["content"][0]
    node_types = {n["type"] for n in para["content"]}
    assert "mention" not in node_types


# ---------------------------------------------------------------------------
# Fenced code blocks must be opaque — nothing inside is interpreted
# ---------------------------------------------------------------------------


def test_code_fence_preserves_at_signs():
    """An ``@mention`` inside a code fence must not become an ADF mention."""
    md = "```\n@admin please review\n```\n"
    adf = json.loads(convert(md, src="md", dst="adf"))
    code_block = adf["content"][0]
    assert code_block["type"] == "codeBlock"
    assert "@admin please review" in code_block["content"][0]["text"]


def test_code_fence_preserves_html_comment_markers():
    """ADF HTML comment markers inside a code fence must stay literal."""
    md = '```\n<!--adf:status text="TODO"/-->\n```\n'
    adf = json.loads(convert(md, src="md", dst="adf"))
    code_block = adf["content"][0]
    assert code_block["type"] == "codeBlock"
    assert "<!--adf:status" in code_block["content"][0]["text"]


def test_code_fence_preserves_envelope_syntax():
    """Envelope-like class names inside code fences stay as code text."""
    md = '```html\n<div class="adf-panel">\n  content\n</div>\n```\n'
    adf = json.loads(convert(md, src="md", dst="adf"))
    code_block = adf["content"][0]
    assert code_block["type"] == "codeBlock"
    assert "adf-panel" in code_block["content"][0]["text"]


def test_code_fence_roundtrips():
    """MD code fence → ADF → MD must preserve inner content exactly."""
    inner = "@user <!--adf:mention/--> [!NOTE]"
    md = f"```\n{inner}\n```\n"
    adf = convert(md, src="md", dst="adf")
    back = convert(adf, src="adf", dst="md")
    assert inner in back


# ---------------------------------------------------------------------------
# Inline code must be opaque
# ---------------------------------------------------------------------------


def test_inline_code_preserves_at_sign():
    """``@admin`` inside backtick code must not become an ADF mention."""
    md = "Run `@admin reset` to fix it.\n"
    adf = json.loads(convert(md, src="md", dst="adf"))
    para = adf["content"][0]
    node_types = {n["type"] for n in para["content"]}
    assert "mention" not in node_types

    code_nodes = [n for n in para["content"] if n.get("type") == "text" and "marks" in n]
    code_texts = [n["text"] for n in code_nodes if any(m["type"] == "code" for m in n["marks"])]
    assert any("@admin reset" in t for t in code_texts)


def test_inline_code_preserves_html_comment():
    """An ADF comment marker inside backticks stays as literal code text."""
    md = 'Use `<!--adf:status text="TODO"/-->` for status.\n'
    adf = json.loads(convert(md, src="md", dst="adf"))
    para = adf["content"][0]
    code_nodes = [n for n in para["content"] if n.get("type") == "text" and "marks" in n]
    code_texts = [n["text"] for n in code_nodes if any(m["type"] == "code" for m in n["marks"])]
    assert any("<!--adf:status" in t for t in code_texts)
