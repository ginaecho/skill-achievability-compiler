"""Check a metadata-only preview-policy repair of an unchanged public HTML template."""
import hashlib
from html import escape
from html.parser import HTMLParser

METADATA = "sickn33__agentic-awesome-skills__fixing-metadata"
DESCRIPTION = "AutoML model evaluation: metrics, visualizations & conclusions (preview)."
PREVIEW_METADATA = {"description": DESCRIPTION, "robots": "noindex, nofollow"}


class _MetadataInsertion(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or len(attrs) != 2 or {key for key, _ in attrs} != {"name", "content"}:
            raise ValueError("Only meta tags with one name and one content attribute may be added")
        fields = dict(attrs)
        name = (fields["name"] or "").lower()
        if name not in PREVIEW_METADATA or name in self.values:
            raise ValueError("Unexpected or duplicate metadata name")
        self.values[name] = fields["content"]

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        if data.strip(" \t\r\n\f"):
            raise ValueError("Only HTML whitespace may surround the inserted meta tags")

    def handle_endtag(self, tag):
        raise ValueError("Closing tags may not be added")

    def handle_comment(self, data):
        raise ValueError("Comments may not be added")

    def handle_decl(self, decl):
        raise ValueError("Declarations may not be added")

    unknown_decl = handle_decl
    handle_pi = handle_decl


def _head_boundary(inputs: dict[str, bytes]) -> tuple[bytes, bytes]:
    if set(inputs) != {"report.html"}:
        raise ValueError("Metadata task requires only the reviewed public HTML template")
    original = inputs["report.html"]
    original.decode("utf-8")
    if original.count(b"<head>") != 1 or original.count(b"</head>") != 1:
        raise ValueError("Expected the reviewed single explicit HTML head")
    prefix, _, tail = original.partition(b"</head>")
    if b"<head>" not in prefix:
        raise ValueError("HTML head boundaries are out of order")
    return prefix, b"</head>" + tail


def metadata_reference(inputs: dict[str, bytes]) -> bytes:
    prefix, suffix = _head_boundary(inputs)
    insertion = "".join(f'    <meta name="{name}" content="{escape(value, quote=True)}">\n'
                        for name, value in PREVIEW_METADATA.items())
    return prefix + insertion.encode("utf-8") + suffix


def verify_preview_metadata(inputs: dict[str, bytes], actual: bytes) -> dict:
    prefix, suffix = _head_boundary(inputs)
    preserved = (len(actual) >= len(prefix) + len(suffix)
                 and actual.startswith(prefix) and actual.endswith(suffix))
    result = {
        "kind": "public_html_preview_metadata_artifact", "passed": False,
        "actual_sha256": hashlib.sha256(actual).hexdigest(),
        "original_bytes_preserved": preserved,
        "external_indexing_or_social_preview_verified": False,
        "access_control_verified": False,
    }
    if not preserved:
        result["error"] = "Original HTML changed outside the allowed insertion before the closing head"
        return result
    parser = _MetadataInsertion()
    try:
        parser.feed(actual[len(prefix):-len(suffix)].decode("utf-8"))
        parser.close()
    except (UnicodeError, ValueError) as error:
        result["error"] = str(error)
        return result
    result["metadata"] = parser.values
    result["passed"] = parser.values == PREVIEW_METADATA
    if not result["passed"]:
        result["error"] = "Description or preview robots policy is missing or differs from the request"
    return result
