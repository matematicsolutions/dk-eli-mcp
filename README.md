# dk-eli-mcp

An MCP server for the Danish **Retsinformation** legal database (`retsinformation.dk`). It
fetches Danish legislation as LexDania 2.1 XML behind native ELI URIs, with verifiable
citations.

Part of the MateMatic `eu-legal-mcp` production line - after PL, DE, AT, ES, FI, IE, NL, SE, FR
and LU. Same citation contract, Retsinformation source. Denmark is ELI-native: every document
has a stable `data.europa.eu/eli`-typed identifier exposed as a `retsinformation.dk/eli/...` URL.

> **Scope.** This MVP grounds Danish documents by ELI coordinate (`year` + `number` in the `lta`
> collection = Lovtidende A) or by accession number, and lists documents changed on a date. The
> API is path-based, not keyword search. It covers laws (LOV), consolidated laws (LBK), executive
> orders (BEK), circulars (CIR) and guidelines (VEJ). Language: Danish. Every response carries a
> `dataset_note`.
>
> **Licence of the data.** Danish legislation in Retsinformation is official public information
> published as Open Data (keyless). This connector relays it with attribution and a `source_url`.

## The tools

| Tool | What it does |
|---|---|
| `dk_get_act` | Metadata for a document by year + number, or by accession. |
| `dk_get_text` | Full LexDania XML of a document (verbatim official text). |
| `dk_recent_changes` | Documents changed on a given date (harvest API). |

Every response carries the contract: `eli_uri` (a full ELI URL, e.g.
`https://www.retsinformation.dk/eli/lta/2018/502`), `human_readable_citation`
(e.g. `Databeskyttelsesloven (LOV nr. 502 af 23/05/2018)`), and `source_url`.

## Install

```bash
cd dk-eli-mcp
pip install -e .
```

## Configure (Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "dk-eli-mcp": { "command": "dk-eli-mcp" }
  }
}
```

Environment:

- `DK_ELI_BASE_URL` - default `https://www.retsinformation.dk`
- `DK_ELI_API_URL` - default `https://api.retsinformation.dk` (harvest API)
- `DK_ELI_CACHE_DIR` - default `~/.matematic/cache/dk-eli`
- `DK_ELI_AUDIT_DIR` - default `~/.matematic/audit`

No API key. Retsinformation open data is keyless.

> The harvest API behind `dk_recent_changes` is only available 03:00-23:45 Danish time. Outside
> that window the tool returns an `upstream_error`; an empty list during the window means nothing
> changed on that date.

## Governance

- **Public data only** - read-only against Retsinformation; no client data leaves the machine.
- **Audit log** - every tool call appends one JSON line to `~/.matematic/audit/dk-eli-mcp.jsonl`.
- **Vendor-neutral** - talks only to `retsinformation.dk`; no LLM provider, no telemetry.
- **Verifiable citations** - every response is independently checkable via `source_url`.

See `CONSTITUTION.md` and `DISCOVERY.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_instructions_drift.py tests/test_parse.py -v   # offline
pytest tests/test_smoke.py -v                                    # hits live Retsinformation
```

## Licence

Apache-2.0. © Matematic Solutions / Wieslaw Mazur.
