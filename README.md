# briefkasten-mcp

MCP server for passing notes ("Zettel") between Claude rooms on one machine
(project chat, Desktop, Claude Code in the editor, and so on). File-based:
each Zettel is a single Markdown file in a mailbox folder that lives outside
the repo. Part of a small series of personal MCP servers — see
[nerdaxe-mcp](https://github.com/andy-builds-ai/nerdaxe-mcp) and
[bitcoin-node-mcp](https://github.com/andy-builds-ai/bitcoin-node-mcp).

Built with the official MCP Python SDK (`mcp`, FastMCP), served over stdio.

## German terms

Tool and field names are German. This glossary maps them to English:

| German | English |
|---|---|
| Briefkasten | mailbox |
| Zettel | note |
| zettel_liste | list notes |
| zettel_lesen | read note |
| zettel_schreiben | write note |
| von / an / inhalt | from / to / content |
| dateiname | filename |
| Von / An / Datum | From / To / Date (the Zettel header) |
| gelesen/ | read (archive folder) |

## Tools

- `zettel_liste(an=None)` — list unread Zettel (filename, sender, recipient,
  timestamp, age), newest first. Optional recipient filter.
- `zettel_lesen(dateiname)` — return the content of one Zettel.
- `zettel_schreiben(von, an, inhalt)` — create a new Zettel and return its
  filename. `inhalt` is the message body only; the `Von/An/Datum` header is
  added automatically. Never overwrites, never deletes.

Archiving (moving to `gelesen/`) is done by hand for now.

## Zettel format

Filename: `YYYY-MM-DD_HHMM_<von>-an-<an>.md`

The body is free-form (handover, report, question — whatever the rooms need);
only the header is fixed, and the server writes it itself. Example of a
session handover:

```markdown
Von: workshop
An: architect
Datum: 2026-07-12 14:30

Working on: ...
Your call: ...
Next: ...
```

## Security model

The server is deliberately narrow about what it can touch:

- **One folder, nothing else.** Every operation stays inside
  `BRIEFKASTEN_PATH`. The path comes from `.env`; the folder (and its
  `gelesen/` subfolder) is created on first start if missing.
- **Every name is validated against a fixed schema.** Room names (`von`,
  `an`) are 1–32 lowercase letters and digits — no separators, no hyphen.
  Filenames handed to `zettel_lesen` must match the exact Zettel scheme.
  That rejects path separators, `..`, absolute paths and drive letters,
  control characters, and Windows device names (`con`, `nul`, …) in one
  step, because none of them fit the pattern. A resolved-path check backs
  it up: the target must resolve to a direct child of the mailbox.
- **Write is create-only.** New Zettel are opened in `"x"` mode, so an
  existing file is never overwritten; a same-minute name collision gets a
  `_2`, `_3`, … suffix. Empty content is rejected.
- **No delete tool by design.** The server can list, read, and create.
  Removing a Zettel is a manual act, not something the model can do.
- **Errors surface as messages, not tracebacks.** Expected failures —
  missing config, an invalid name, a missing or unreadable Zettel, a folder
  that can't be created, a write that can't complete — are caught and
  returned as a plain explanation instead of raising.

## Setup

Requires Python 3.10 or newer.

Windows:

    py -m venv .venv
    .venv\Scripts\pip install -r requirements.txt

Linux / macOS:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Then copy `.env.example` to `.env` and set `BRIEFKASTEN_PATH` to an absolute
path for the mailbox folder (outside the repo).

## Usage

Run directly for local testing:

    .venv\Scripts\python server.py

Or wire it into an MCP client config as `briefkasten`, using the absolute
path to the venv's Python and to `server.py`.

## Testing

Verified along the build's review chain:

1. Direct function calls covering the normal case, edge cases, and forced
   error paths (missing `BRIEFKASTEN_PATH`, invalid names, path-escape
   attempts, name collisions, empty content).
2. A programmatic MCP client over stdio, exercising the three tools through
   the real protocol.
3. A cold closing review through an isolated reviewer (2× Sonnet, correctness
   and security). Four findings were fixed.

## Limits

- Single mailbox on one machine, no networking.
- No delete or archive tool — `gelesen/` is tidied by hand.
- No search or full-text index; `zettel_liste` lists, `zettel_lesen` reads.
