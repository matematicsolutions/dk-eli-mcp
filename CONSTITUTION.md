# Constitution of dk-eli-mcp

Version: 0.1.0
Date: 2026-06-29
Licence: Apache-2.0

`dk-eli-mcp` is an MCP server for the Danish Retsinformation legal database
(`retsinformation.dk`). It fetches Danish legislation as LexDania 2.1 XML behind native ELI
URIs, with verifiable citations. The MVP grounds documents by ELI coordinate or accession and
lists documents changed on a date; case law is a later feature.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV).

---

## Art. 1. Public data only

Retsinformation is the official, public source of Danish legislation, published as Open Data
(keyless). The server is read-only against Retsinformation and sends nothing beyond the requested
coordinates / date.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/dk-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to write =
the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server talks
only to `retsinformation.dk` (and `api.retsinformation.dk`) and the local filesystem.
Authentication: none; own backoff + cache.

## Art. 4. ELI citations and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: the canonical ELI URL, built from the document's own metadata
  (`retsinformation.dk/eli/lta/{year}/{number}`, or `/eli/accn/{accession}`). NEVER invented.
- `human_readable_citation`: Danish convention (e.g. "Databeskyttelsesloven (LOV nr. 502 af
  23/05/2018)").
- `source_url`: the fetchable ELI page on retsinformation.dk.

---

## Open points

1. **Keyword search** - the API is path-based (ELI coordinate / accession); discovery of recent
   documents is via the harvest API (`dk_recent_changes`). There is no free-text search.
2. **Harvest API window** - `api.retsinformation.dk` is only available 03:00-23:45 Danish time.
3. **Case law** - Danish court decisions (Domsdatabasen, Højesteret) are a later feature, not in
   this legislation MVP.

## Ewolucja konstytucji

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-06-29. Author: Wieslaw Mazur / MateMatic.
