"""Offline parse tests - build_record against a committed LexDania fixture (no network)."""

from __future__ import annotations

from pathlib import Path

from dk_eli_mcp.citations import build_record, parse_meta

FIXTURE = Path(__file__).parent / "fixtures" / "bek_2024_227.xml"
BASE = "https://www.retsinformation.dk"


def _xml() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_meta_core_fields():
    meta = parse_meta(_xml())
    assert meta["document_type"] == "BEK"
    assert meta["accession_number"] == "B20240022705"
    assert meta["year"] == 2024
    assert meta["number"] == 227
    assert meta["date_signed"] == "2024-03-07"
    assert meta["status"] == "Historic"
    assert meta["announced_in"] == "Lovtidende A"
    assert meta["title"] and meta["title"].lower().startswith("bek")


def test_build_record_from_coordinates():
    rec = build_record(_xml(), BASE, year=2024, number=227)
    assert rec["eli_uri"] == "https://www.retsinformation.dk/eli/lta/2024/227"
    assert rec["source_url"] == rec["eli_uri"]
    # No PopularTitle in this BEK -> citation falls back to the full DocumentTitle.
    assert rec["human_readable_citation"] is not None
    assert "BEK nr. 227 af 07/03/2024" in rec["human_readable_citation"]


def test_build_record_backfills_coordinates_from_meta():
    # Caller has only the accession; year/number come from <Meta>.
    rec = build_record(_xml(), BASE, accession="B20240022705")
    assert rec["year"] == 2024
    assert rec["number"] == 227
    # With year+number recovered, the canonical lta ELI is preferred over the accession form.
    assert rec["eli_uri"] == "https://www.retsinformation.dk/eli/lta/2024/227"
    assert rec["accession_number"] == "B20240022705"


def test_unicode_declaration_does_not_break_parsing():
    # The fixture XML carries `<?xml ... encoding="utf-8"?>`; parse_meta must not raise.
    meta = parse_meta(_xml())
    assert meta != {}
