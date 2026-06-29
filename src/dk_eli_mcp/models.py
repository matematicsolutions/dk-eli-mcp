"""Pydantic v2 models for the Danish Retsinformation API + dk-eli-mcp."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "Retsinformation serves Danish consolidated legislation as LexDania 2.1 XML behind "
    "native ELI URIs. Address a document by ELI coordinate (year + number in the 'lta' "
    "collection = Lovtidende A) or by its accession number; there is no free-text search. "
    "dk_recent_changes lists documents changed on a given date via the harvest API "
    "(available 03:00-23:45 Danish time). Covers laws (LOV), consolidated laws (LBK), "
    "executive orders (BEK), circulars (CIR) and guidelines (VEJ). Language: Danish."
)

AVAILABILITY_NOTE = (
    "The harvest API (api.retsinformation.dk) is only available 03:00-23:45 Danish time; "
    "outside that window it returns an error. An empty list means no documents changed on "
    "that date, which is a valid result."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Act(_Tolerant):
    """A Danish legal act (parsed from LexDania XML metadata)."""

    year: int | None = None
    number: int | None = None
    accession_number: str | None = None
    title: str | None = None
    popular_title: str | None = None
    document_type: str | None = None
    status: str | None = None
    date_signed: str | None = None
    date_published: str | None = None
    ministry: str | None = None
    announced_in: str | None = None

    # Citation contract (Art. 4 CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    dataset_note: str = DATASET_NOTE


class LawText(_Tolerant):
    """Result of ``dk_get_text`` (full LexDania XML, verbatim)."""

    year: int | None = None
    number: int | None = None
    accession_number: str | None = None
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None
    format: str = "lex-dania-xml"
    content: str | None = None
    byte_size: int | None = None
    dataset_note: str = DATASET_NOTE


class RecentChange(_Tolerant):
    """A single document-change entry from the harvest API."""

    accession_number: str | None = None
    document_type: str | None = None
    change_date: str | None = None
    reason_for_change: str | None = None
    eli_uri: str | None = None
    source_url: str | None = None


class RecentChangesResult(_Tolerant):
    """Result of ``dk_recent_changes``."""

    date: str
    total: int
    items: list[RecentChange] = Field(default_factory=list)
    availability_note: str = AVAILABILITY_NOTE
    dataset_note: str = DATASET_NOTE
