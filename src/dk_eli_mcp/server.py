"""FastMCP entry point - Danish Retsinformation tools.

Run:

    python -m dk_eli_mcp.server

Configuration via env:

- ``DK_ELI_CACHE_DIR`` (default ``~/.matematic/cache/dk-eli``)
- ``DK_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``DK_ELI_BASE_URL`` (default ``https://www.retsinformation.dk``)
- ``DK_ELI_API_URL`` (default ``https://api.retsinformation.dk``)
"""

from __future__ import annotations

import os
import re

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import build_record
from .client import DEFAULT_API_URL, DEFAULT_BASE_URL, RetsinfoClient
from .models import Act, LawText, RecentChange, RecentChangesResult

INSTRUCTIONS = """\
This MCP server exposes the Danish Retsinformation legal database (retsinformation.dk), the official source of Danish legislation, published as Open Data. Denmark is ELI-native: every document has a stable ELI URL. The server grounds Danish acts by ELI coordinate (year + number in the `lta` collection = Lovtidende A) or by accession number, and lists documents changed on a date. Every response carries a stable `eli_uri`, a `human_readable_citation` and a `source_url` (the citation contract).

## Call order

1. `dk_get_act` - metadata for a document by `year` + `number` (e.g. the data protection act is `year=2018, number=502`) or by `accession` (e.g. `A20180050230`). Returns `eli_uri` (e.g. `https://www.retsinformation.dk/eli/lta/2018/502`), title, Danish citation, dates, status.
2. `dk_get_text` - the full LexDania XML of a document by the same coordinates (verbatim official text).
3. `dk_recent_changes` - the documents changed on a given `date` (`YYYY-MM-DD`) via the harvest API; each entry carries its accession number and `eli_uri`. Feed an accession back into `dk_get_act` / `dk_get_text`.

## Hard constraints

- **No free-text search** - addressed by ELI coordinate (year + number) or accession, not keywords. You must know the coordinates (a Danish citation gives them, e.g. "LOV nr. 502 af 23/05/2018"); or discover recent ones via `dk_recent_changes`. Relay the `dataset_note`.
- **ELI is the key to citability** - the ELI is the retsinformation.dk/eli/... URL; do not invent it. It is built from the document's own metadata.
- **Verbatim text** - `dk_get_text` returns the official LexDania XML unchanged; do not paraphrase the law as if it were the text.
- **Harvest API window** - `dk_recent_changes` only works 03:00-23:45 Danish time; an empty list is a valid "nothing changed" result, not an error. Relay the `availability_note`.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/dk-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or invalid (e.g. neither (year, number) nor accession given, bad year, malformed date).
- `not_found` - no document exists for those coordinates.
- `upstream_error` - a Retsinformation error (HTTP, timeout, malformed XML) or the harvest API being out of hours. Retry once before surfacing.

## Response style

- Cite as `human_readable_citation` with the ELI URL: "Databeskyttelsesloven (LOV nr. 502 af 23/05/2018), https://www.retsinformation.dk/eli/lta/2018/502".
- NEVER invent an ELI, a number, an accession or a year - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for dk-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="dk-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("DK_ELI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _api_url() -> str:
    return os.environ.get("DK_ELI_API_URL", DEFAULT_API_URL).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No document found in Retsinformation for those coordinates.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"Retsinformation error: {type(exc).__name__}: {exc}")
    return exc


def _resolve_coordinates(
    year: int | None, number: int | None, accession: str | None
) -> tuple[int | None, int | None, str | None]:
    """Validate that the caller gave usable coordinates: (year AND number) OR accession."""
    if accession:
        accession = accession.strip()
        if not re.fullmatch(r"[A-Za-z]\d{6,}", accession):
            raise ToolError(
                "invalid_arg",
                f"accession={accession!r} looks malformed (expected e.g. 'A20180050230').",
            )
        return None, None, accession
    if year is None or number is None:
        raise ToolError(
            "invalid_arg",
            "Provide either (year and number) or accession.",
        )
    if not 1600 <= year <= 2100:
        raise ToolError("invalid_arg", f"year={year} is out of range (1600..2100).")
    if number <= 0:
        raise ToolError("invalid_arg", f"number={number} must be positive.")
    return year, number, None


async def _fetch_xml(
    client: RetsinfoClient, year: int | None, number: int | None, accession: str | None
) -> str:
    if accession:
        return await client.get_act_xml_by_accession(accession)
    assert year is not None and number is not None
    return await client.get_act_xml(year, number)


# ---------------------------------------------------------------------------
# dk_get_act
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def dk_get_act(
    year: int | None = None, number: int | None = None, accession: str | None = None
) -> Act:
    """Fetch Danish act / order metadata by ELI coordinate or accession.

    Args:
        year: e.g. ``2018`` (use together with ``number``).
        number: e.g. ``502`` (use together with ``year``).
        accession: e.g. ``"A20180050230"`` (alternative to year + number).

    Returns:
        ``Act`` with ``eli_uri``, ``human_readable_citation``, ``source_url``.
    """
    audit = _audit()
    year, number, accession = _resolve_coordinates(year, number, accession)
    input_hash = hash_input({"year": year, "number": number, "accession": accession})

    with timer() as t:
        try:
            async with RetsinfoClient(base_url=_base_url(), api_url=_api_url()) as client:
                xml = await _fetch_xml(client, year, number, accession)
        except Exception as exc:
            audit.log(tool="dk_get_act", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    record = build_record(xml, _base_url(), year=year, number=number, accession=accession)
    if not record.get("eli_uri"):
        raise ToolError("not_found", "Document has no resolvable ELI metadata.")
    act = Act.model_validate(record)
    audit.log(tool="dk_get_act", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return act


# ---------------------------------------------------------------------------
# dk_get_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def dk_get_text(
    year: int | None = None, number: int | None = None, accession: str | None = None
) -> LawText:
    """Fetch the full LexDania XML of a Danish document (verbatim official text).

    Args:
        year: e.g. ``2018`` (use together with ``number``).
        number: e.g. ``502`` (use together with ``year``).
        accession: e.g. ``"A20180050230"`` (alternative to year + number).

    Returns:
        ``LawText`` with the citation contract and ``content`` (LexDania XML).
    """
    audit = _audit()
    year, number, accession = _resolve_coordinates(year, number, accession)
    input_hash = hash_input({"year": year, "number": number, "accession": accession})

    with timer() as t:
        try:
            async with RetsinfoClient(base_url=_base_url(), api_url=_api_url()) as client:
                xml = await _fetch_xml(client, year, number, accession)
        except Exception as exc:
            audit.log(tool="dk_get_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    record = build_record(xml, _base_url(), year=year, number=number, accession=accession)
    result = LawText(
        year=record.get("year"),
        number=record.get("number"),
        accession_number=record.get("accession_number"),
        eli_uri=record.get("eli_uri"),
        human_readable_citation=record.get("human_readable_citation"),
        source_url=record.get("source_url"),
        content=xml,
        byte_size=len(xml.encode("utf-8")),
    )
    audit.log(tool="dk_get_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# dk_recent_changes
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def dk_recent_changes(date: str) -> RecentChangesResult:
    """List Danish documents changed on a given date (harvest API).

    Args:
        date: ``YYYY-MM-DD`` (e.g. ``"2026-06-26"``). The harvest API is available
            03:00-23:45 Danish time; an empty list is a valid "nothing changed" result.

    Returns:
        ``RecentChangesResult`` with ``items`` - each ``RecentChange`` carries an accession
        number and ``eli_uri`` you can feed back into ``dk_get_act`` / ``dk_get_text``.
    """
    audit = _audit()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date.strip()):
        raise ToolError("invalid_arg", f"date={date!r} must be YYYY-MM-DD.")
    date = date.strip()
    input_hash = hash_input({"date": date})

    with timer() as t:
        try:
            async with RetsinfoClient(base_url=_base_url(), api_url=_api_url()) as client:
                raw = await client.recent_changes(date)
        except Exception as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
                err: Exception = ToolError(
                    "upstream_error",
                    "Harvest API returned 400 - it is only available 03:00-23:45 Danish time, "
                    "or the date is invalid. Retry within that window.",
                )
            else:
                err = _map_upstream(exc)
            audit.log(tool="dk_recent_changes", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise err from exc

    base = _base_url()
    items: list[RecentChange] = []
    for entry in raw:
        accession = entry.get("accessionsnummer") or None
        doc_type = None
        dt = entry.get("documentType")
        if isinstance(dt, dict):
            doc_type = dt.get("shortName")
        eli = f"{base}/eli/accn/{accession}" if accession else None
        items.append(
            RecentChange(
                accession_number=accession,
                document_type=doc_type,
                change_date=entry.get("changeDate"),
                reason_for_change=entry.get("reasonForChange"),
                eli_uri=eli,
                source_url=eli,
            )
        )

    result = RecentChangesResult(date=date, total=len(items), items=items)
    audit.log(tool="dk_recent_changes", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
