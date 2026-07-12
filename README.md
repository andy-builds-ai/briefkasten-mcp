# briefkasten-mcp

MCP server for passing notes ("Zettel") between Claude rooms on this machine
(claude.ai project chat, Claude Desktop, Claude Code in VS Code, classroom).
File-based: each Zettel is one Markdown file in a mailbox folder outside
repo and vault. Local only — no remote, no push.

## Tools

- `zettel_liste(an=None)` — list unread Zettel (filename, sender, recipient,
  age). Optional recipient filter.
- `zettel_lesen(dateiname)` — return the content of one Zettel.
- `zettel_schreiben(von, an, inhalt)` — create a new Zettel and return its
  filename. `inhalt` is the message body only; the `Von/An/Datum` header is
  added automatically. Never overwrites, never deletes.

Archiving (moving to `gelesen/`) is done by hand for now.

## Zettel format

Filename: `YYYY-MM-DD_HHMM_<von>-an-<an>.md`

```markdown
Von: werkstatt
An: architekt
Datum: 2026-07-12 14:30

Woran: ...
Deine Hand offen: ...
Als nächstes: ...
```

## Setup

```
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # then set BRIEFKASTEN_PATH
```

The mailbox folder (with subfolder `gelesen/`) is created on first start
if missing.
