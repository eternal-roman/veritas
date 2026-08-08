"""N0 extract: versioned, deterministic body → normalized text."""

from __future__ import annotations

from veritas.hashing import normalize_content
from veritas.notary.extract import EXTRACT_VERSION, ExtractedBody, extract_body


def test_extract_version_is_stable_and_namespaced():
    assert EXTRACT_VERSION.startswith("veritas.extract.")
    assert EXTRACT_VERSION == "veritas.extract.v1"


def test_plain_text_is_normalized_and_deterministic():
    raw = b"  hello\r\n\r\n\r\nworld\t\t  "
    first = extract_body(raw, content_type="text/plain; charset=utf-8")
    second = extract_body(raw, content_type="text/plain; charset=utf-8")
    assert first == second
    assert isinstance(first, ExtractedBody)
    assert first.extract_version == EXTRACT_VERSION
    assert first.media_kind == "text"
    assert first.text == normalize_content("hello\n\nworld")
    assert first.charset == "utf-8"


def test_html_strips_script_and_style_deterministically():
    html = b"""<!DOCTYPE html>
    <html><head>
      <title>Example Title</title>
      <style>body { color: red; }</style>
      <script>alert("nope")</script>
    </head>
    <body>
      <p>Visible paragraph.</p>
      <script>document.write("hidden")</script>
      <div>More text</div>
    </body></html>"""
    a = extract_body(html, content_type="text/html; charset=utf-8")
    b = extract_body(html, content_type="text/html; charset=utf-8")
    assert a == b
    assert a.media_kind == "html"
    assert a.title == "Example Title"
    assert "Visible paragraph." in a.text
    assert "More text" in a.text
    assert "alert" not in a.text
    assert "document.write" not in a.text
    assert "color: red" not in a.text
    assert a.extract_version == EXTRACT_VERSION


def test_same_logical_html_with_crlf_is_stable_after_normalize():
    """Line endings and cosmetic whitespace must not change the extract."""
    lf = b"<html><body><p>One</p>\n<p>Two</p></body></html>"
    crlf = b"<html><body><p>One</p>\r\n<p>Two</p></body></html>"
    assert extract_body(lf, content_type="text/html").text == extract_body(
        crlf, content_type="text/html"
    ).text


def test_str_body_accepted_without_redecode():
    out = extract_body("plain already", content_type="text/plain")
    assert out.text == "plain already"
    assert out.charset == "utf-8"


def test_charset_from_content_type_is_honoured():
    # latin-1: 0xe9 is é
    body = b"caf\xe9"
    out = extract_body(body, content_type="text/plain; charset=latin-1")
    assert out.text == "café"
    assert out.charset == "latin-1"


def test_unknown_content_type_falls_back_to_text_decode():
    out = extract_body(b"raw bytes", content_type="application/octet-stream")
    assert out.media_kind == "text"
    assert out.text == "raw bytes"


def test_empty_body_is_stable():
    out = extract_body(b"", content_type="text/plain")
    assert out.text == ""
    assert out.extract_version == EXTRACT_VERSION
