"""Smoke tests - require internet, hit the live Danish Retsinformation API.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

from datetime import date

import pytest

from dk_eli_mcp.server import dk_get_act, dk_get_text, dk_recent_changes

# Databeskyttelsesloven (the Danish data protection act) - LOV nr. 502 af 23/05/2018.
YEAR, NUMBER = 2018, 502
ACCESSION = "A20180050230"


@pytest.mark.asyncio
async def test_smoke_get_act_by_coordinate() -> None:
    act = await dk_get_act(YEAR, NUMBER)
    assert act.eli_uri == "https://www.retsinformation.dk/eli/lta/2018/502"
    assert act.document_type == "LOV"
    assert act.number == 502
    assert act.year == 2018
    assert act.accession_number == ACCESSION
    assert act.human_readable_citation
    assert "LOV nr. 502 af 23/05/2018" in act.human_readable_citation
    assert act.source_url and act.source_url.startswith("https://")


@pytest.mark.asyncio
async def test_smoke_get_act_by_accession() -> None:
    act = await dk_get_act(accession=ACCESSION)
    # Year/number are backfilled from <Meta>, so the canonical lta ELI is returned.
    assert act.eli_uri == "https://www.retsinformation.dk/eli/lta/2018/502"
    assert act.popular_title == "Databeskyttelsesloven"


@pytest.mark.asyncio
async def test_smoke_get_text() -> None:
    text = await dk_get_text(YEAR, NUMBER)
    assert text.format == "lex-dania-xml"
    assert text.content and "databeskyttelsesloven" in text.content.lower()
    assert text.eli_uri == "https://www.retsinformation.dk/eli/lta/2018/502"
    assert text.byte_size and text.byte_size > 1000


@pytest.mark.asyncio
async def test_smoke_recent_changes() -> None:
    # A recent weekday; the harvest API needs to be within 03:00-23:45 CET to return data.
    day = (date(2026, 6, 26)).isoformat()
    result = await dk_recent_changes(day)
    assert result.date == day
    assert isinstance(result.items, list)
    # If the window is open and that date had changes, entries carry an accession + ELI.
    for item in result.items[:3]:
        assert item.accession_number
        assert item.eli_uri and item.eli_uri.startswith("https://www.retsinformation.dk/eli/accn/")
