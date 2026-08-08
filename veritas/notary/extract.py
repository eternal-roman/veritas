"""Versioned, deterministic body → normalized text for the evidence notary.

N0-H: every record stamps ``extract_version`` so two notaries that disagree can
name the algorithm. The transform is pure: no wall clock, no randomness, no
locale. Same bytes + content-type always yield the same ``ExtractedBody``.

This is deliberately stdlib-only (no trafilatura/readability). v1 is a named
HTML-to-text strip of script/style plus the same normalisation used for
content hashes — not main-content heuristics that drift across libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from html.parser import HTMLParser
from typing import Literal

from veritas.hashing import normalize_content

# Bump when the algorithm changes in a way that can alter extracted text for
# the same input. Records carry this string; re-extract under a new version
# is a new observation, not a silent rewrite.
EXTRACT_VERSION = "veritas.extract.v1"

MediaKind = Literal["html", "text"]

_BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
    "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
})
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template"})


@dataclass(frozen=True)
class ExtractedBody:
    """Deterministic extract of a response body."""

    text: str
    media_kind: MediaKind
    extract_version: str
    charset: str
    title: str | None = None


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text and the document title; drop script/style trees."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if name == "title":
            self._in_title = True
            return
        if name == "br" or name in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if name == "title":
            self._in_title = False
            return
        if name in _BLOCK_TAGS and name != "br":
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self._title_parts.append(data)
            return
        self._chunks.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS or self._skip_depth:
            return
        if name == "br" or name in _BLOCK_TAGS:
            self._chunks.append("\n")

    @property
    def title(self) -> str | None:
        raw = "".join(self._title_parts)
        cleaned = normalize_content(raw)
        return cleaned or None

    @property
    def text(self) -> str:
        return normalize_content("".join(self._chunks))


def _parse_content_type(content_type: str | None) -> tuple[str | None, str | None]:
    """Return (media_type_lower, charset_lower) from a Content-Type header value."""
    if not content_type or not content_type.strip():
        return None, None
    msg = Message()
    msg["content-type"] = content_type
    charset = msg.get_content_charset()
    charset_out = charset.lower() if charset else None
    # Prefer the raw type token so we do not invent text/plain when the header
    # was only a charset parameter or empty type.
    media_token = content_type.split(";", 1)[0].strip().lower()
    if "/" not in media_token:
        return None, charset_out
    return media_token, charset_out

def _decode_body(body: bytes | str, charset: str | None) -> tuple[str, str]:
    if isinstance(body, str):
        return body, charset or "utf-8"
    encoding = charset or "utf-8"
    try:
        return body.decode(encoding), encoding
    except LookupError:
        return body.decode("utf-8", errors="replace"), "utf-8"
    except UnicodeDecodeError:
        return body.decode(encoding, errors="replace"), encoding


def _is_html(media_type: str | None, text: str) -> bool:
    if media_type:
        if media_type in ("text/html", "application/xhtml+xml") or media_type.endswith("+html"):
            return True
        if media_type.startswith("text/") or media_type in (
            "application/json",
            "application/xml",
            "text/xml",
        ):
            return False
    sample = text.lstrip()[:256].lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html")


def extract_body(
    body: bytes | str,
    *,
    content_type: str | None = None,
    charset: str | None = None,
) -> ExtractedBody:
    """Extract normalized text from a fetched body.

    Parameters
    ----------
    body:
        Raw response body (bytes) or already-decoded text.
    content_type:
        HTTP Content-Type header value when known.
    charset:
        Explicit charset override; otherwise taken from content_type or utf-8.
    """
    media_type, ct_charset = _parse_content_type(content_type)
    resolved_charset = charset or ct_charset
    text, used_charset = _decode_body(body, resolved_charset)

    if _is_html(media_type, text):
        parser = _HTMLTextExtractor()
        parser.feed(text)
        parser.close()
        return ExtractedBody(
            text=parser.text,
            media_kind="html",
            extract_version=EXTRACT_VERSION,
            charset=used_charset,
            title=parser.title,
        )

    return ExtractedBody(
        text=normalize_content(text),
        media_kind="text",
        extract_version=EXTRACT_VERSION,
        charset=used_charset,
        title=None,
    )
