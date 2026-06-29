"""Danish Retsinformation (LexDania XML) parsing + citation helpers.

Retsinformation serves legislation as LexDania 2.1 XML (no XML namespace; the root
``<Dokument>`` carries only a ``SchemaLocation`` attribute). The document is genuinely
ELI-native: the HTML rendering exposes the ``data.europa.eu/eli/ontology`` RDFa prefix and
the canonical ELI is ``retsinformation.dk/eli/lta/{year}/{number}``.

We parse the ``<Meta>`` block with the stdlib ElementTree - no third-party XML dep.

Citation contract:
- ``eli_uri``: the canonical ELI URL built from the act's year + number (lta collection),
  or from the accession number when year/number are absent. NEVER invented - both come from
  the document's own ``<Meta>``.
- ``human_readable_citation``: Danish convention, e.g. "Databeskyttelsesloven
  (LOV nr. 502 af 23/05/2018)".
- ``source_url``: the fetchable ELI page on retsinformation.dk.

NOTE: ``ET.fromstring`` is fed UTF-8 *bytes* (not a str) because the XML carries an
``encoding="utf-8"`` declaration, which ElementTree rejects on unicode input.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

# Document types recognised in Retsinformation.
DOC_TYPES = ("LOV", "LBK", "BEK", "CIR", "VEJ", "SKR")


def _normalize_doc_type(raw: str | None) -> str | None:
    """Turn a raw DocumentType like 'LOV H#LOKDOK 01' or 'BEK H#LOKDOK04' into 'LOV' / 'BEK'."""
    if not raw:
        return None
    head = raw.strip().upper().split()[0]
    for code in DOC_TYPES:
        if head.startswith(code):
            return code
    return head or None


def _iso_to_dk(date_iso: str | None) -> str | None:
    """Reformat an ISO date '2018-05-23' to the Danish citation form '23/05/2018'."""
    if not date_iso:
        return None
    parts = date_iso.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        y, m, d = parts
        return f"{d}/{m}/{y}"
    return date_iso


def _text(meta: ET.Element, tag: str) -> str | None:
    el = meta.find(tag)
    if el is not None and el.text and el.text.strip():
        return el.text.strip()
    return None


def parse_meta(xml_text: str) -> dict[str, Any]:
    """Parse the ``<Meta>`` block of a LexDania document into a flat dict."""
    out: dict[str, Any] = {}
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        return out
    meta = root.find(".//Meta")
    if meta is None:
        return out

    out["document_type"] = _normalize_doc_type(_text(meta, "DocumentType"))
    out["accession_number"] = _text(meta, "AccessionNumber")
    out["title"] = _text(meta, "DocumentTitle")
    out["popular_title"] = _text(meta, "PopularTitle")
    out["status"] = _text(meta, "Status")
    out["ministry"] = _text(meta, "Ministry")
    out["announced_in"] = _text(meta, "AnnouncedIn")
    out["date_signed"] = _text(meta, "DiesSigni")
    out["date_published"] = _text(meta, "DiesEdicti")

    year = _text(meta, "Year")
    number = _text(meta, "Number")
    if year and year.isdigit():
        out["year"] = int(year)
    if number and number.isdigit():
        out["number"] = int(number)

    return out


def build_record(
    xml_text: str,
    base_url: str,
    *,
    year: int | None = None,
    number: int | None = None,
    accession: str | None = None,
) -> dict[str, Any]:
    """Build a citation-bearing record from a LexDania document.

    ``year``/``number``/``accession`` are the coordinates the caller used; any missing one is
    backfilled from the document's own ``<Meta>``.
    """
    meta = parse_meta(xml_text)

    year = year if year is not None else meta.get("year")
    number = number if number is not None else meta.get("number")
    accession = accession or meta.get("accession_number")

    # Canonical ELI: prefer the lta coordinate form, fall back to accession.
    if year is not None and number is not None:
        eli_uri = f"{base_url}/eli/lta/{year}/{number}"
    elif accession:
        eli_uri = f"{base_url}/eli/accn/{accession}"
    else:
        eli_uri = None

    name = meta.get("popular_title") or meta.get("title")
    doc_type = meta.get("document_type")
    dk_date = _iso_to_dk(meta.get("date_signed"))

    formal_parts = []
    if doc_type:
        formal_parts.append(doc_type)
    if number is not None:
        formal_parts.append(f"nr. {number}")
    if dk_date:
        formal_parts.append(f"af {dk_date}")
    formal = " ".join(formal_parts) if formal_parts else None

    if name and formal:
        human = f"{name} ({formal})"
    elif name:
        human = name
    else:
        human = formal

    record: dict[str, Any] = {
        "year": year,
        "number": number,
        "accession_number": accession,
        "title": meta.get("title"),
        "popular_title": meta.get("popular_title"),
        "document_type": doc_type,
        "status": meta.get("status"),
        "date_signed": meta.get("date_signed"),
        "date_published": meta.get("date_published"),
        "ministry": meta.get("ministry"),
        "announced_in": meta.get("announced_in"),
        "eli_uri": eli_uri,
        "human_readable_citation": human,
        "source_url": eli_uri,
    }
    return record
