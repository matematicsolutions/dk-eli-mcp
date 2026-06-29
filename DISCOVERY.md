# DISCOVERY - dk-eli-mcp (Denmark / Retsinformation)

Date: 2026-06-29. Source selection driven by Legal Data Hunter coverage data
(`worldwidelaw/legal-sources`): Denmark is a `has_consolidated_codes` jurisdiction with a clean,
keyless, **ELI-native** machine path - confirmed by live probes below.

## Why Denmark, why now

An earlier sweep of the `eu-legal-mcp` line tentatively rejected DK ("eli + /api return HTML, not
data"). That was a **path error**: the HTML lives at `/eli/lta/{year}/{number}` (no suffix), the
machine XML at `/eli/lta/{year}/{number}/xml`, and the harvest API on a **separate host**
(`api.retsinformation.dk`). Legal Data Hunter's own crawler config and live probes confirm a clean
source: native ELI plus XML, keyless, the same tier as FI and LU.

## Endpoints (all keyless, Open Data)

| Purpose | Endpoint | Format |
|---|---|---|
| Document by ELI coordinate | `https://www.retsinformation.dk/eli/lta/{year}/{number}/xml` | LexDania 2.1 XML |
| Document by accession | `https://www.retsinformation.dk/eli/accn/{accession}/xml` | LexDania 2.1 XML |
| HTML rendering (RDFa, `eli` ontology) | `https://www.retsinformation.dk/eli/lta/{year}/{number}` | HTML+RDFa |
| Documents changed on a date | `https://api.retsinformation.dk/v1/Documents?date=YYYY-MM-DD` | JSON |
| Discovery (full corpus) | `https://retsinformation.dk/sitemap.xml` (21 pages, ~20k ELI URLs) | XML sitemap |

- `lta` = Lovtidende A (the official gazette collection). Covers LOV / LBK / BEK / CIR / VEJ.
- Harvest API is available **03:00-23:45 Danish time**; out-of-hours returns HTTP 400. A 200 with
  `[]` means nothing changed on that date (valid).
- 404 for a non-existent coordinate is clean.

## XML shape (LexDania 2.1)

Root `<Dokument>` has **no XML namespace** (only a `SchemaLocation` attribute), so stdlib
ElementTree parses it directly. The `<Meta>` block carries: `DocumentType` (e.g. `LOV H#LOKDOK 01`
-> normalised `LOV`), `AccessionNumber`, `DocumentTitle`, `PopularTitle` (when present),
`Year`, `Number`, `DiesSigni` (signature/enactment date, ISO), `DiesEdicti` (publication date),
`Status` (`Valid` / `Historic`), `AnnouncedIn`, `Ministry`, `Signature`. Full text is in `<Char>`
elements within `<Linea>` / `<Titel>` and the `<Bog>/<Afsnit>/<Kapitel>` structure.

> **Gotcha.** The XML declares `<?xml version="1.0" encoding="utf-8"?>`. `ET.fromstring` rejects an
> encoding declaration on a `str`; we feed it UTF-8 **bytes** (`xml_text.encode("utf-8")`).

## Citation contract (Art. 4)

- `eli_uri` = `https://www.retsinformation.dk/eli/lta/{year}/{number}` (canonical), or
  `/eli/accn/{accession}` when year/number are unavailable. `<Meta>` always carries Year + Number,
  so an accession lookup still resolves to the canonical lta ELI.
- `human_readable_citation` = `{PopularTitle | DocumentTitle} ({TYPE} nr. {Number} af {DD/MM/YYYY})`,
  e.g. "Databeskyttelsesloven (LOV nr. 502 af 23/05/2018)".
- `source_url` = the ELI page on retsinformation.dk.

## Tools (MVP)

- `dk_get_act(year, number | accession)` - metadata.
- `dk_get_text(year, number | accession)` - verbatim LexDania XML.
- `dk_recent_changes(date)` - harvest API list of changed documents (feed accessions back in).

## Deferred

- **Case law / ECLI** - Domsdatabasen / Højesteret (separate sources; feature 002 candidate).
- **Full-corpus listing** via the sitemap (20k URLs) - not exposed as a tool in the MVP (would be a
  heavy crawl); `dk_recent_changes` covers incremental discovery.
- **Plain-text extraction** - the MVP returns the verbatim XML; a flattened-text option could be
  added later.

## Licence / re-use

Danish legislation is official public information; Retsinformation publishes it as Open Data
(see `retsinformation.dk/eli/about`). Read-only relay with attribution + `source_url`. No key, no
ToS gate for the open endpoints. Distribution as a public connector is in line with the
keyless/no-auth tier.
