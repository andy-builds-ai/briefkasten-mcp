"""Briefkasten MCP server.

File-based note passing ("Zettel") between Claude rooms on this machine.
Each Zettel is one Markdown file in the mailbox folder (BRIEFKASTEN_PATH,
outside repo and vault). The server only ever touches that folder.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("briefkasten")

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("briefkasten")

# Room names (von/an): 1–32 lowercase letters and digits — nothing else,
# because they become part of a filename. No hyphen, so the "-an-" separator
# inside the filename stays unambiguous. \Z (not $) anchors the true end of
# string: $ also matches just before a trailing newline, so "werkstatt\n"
# would otherwise slip through. The length cap keeps the built filename
# inside the Windows path limit.
NAME_PATTERN = re.compile(r"^[a-z0-9]{1,32}\Z")

# Zettel filename: 2026-07-11_1430_werkstatt-an-architekt.md
# (optional _2 suffix before .md when the same minute produces a collision)
FILENAME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d{4})_([a-z0-9]+)-an-([a-z0-9]+)(?:_(\d+))?\.md\Z"
)


class BriefkastenError(Exception):
    """Expected error with a message meant for the caller, not a traceback."""


def _briefkasten() -> Path:
    """Return the mailbox folder, creating it (and gelesen/) if missing."""
    raw = os.getenv("BRIEFKASTEN_PATH")
    if not raw:
        raise BriefkastenError(
            "BRIEFKASTEN_PATH ist nicht gesetzt — bitte in der .env "
            "neben server.py eintragen."
        )
    folder = Path(raw)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gelesen").mkdir(exist_ok=True)
    except OSError as exc:
        raise BriefkastenError(
            f"Briefkasten-Ordner '{folder}' konnte nicht angelegt werden: {exc}"
        )
    return folder


def _validate_name(value: str, field: str) -> str:
    """Validate a room name (von/an). Returns it unchanged if valid."""
    if not value or not NAME_PATTERN.match(value):
        raise BriefkastenError(
            f"Ungültiger Wert für '{field}': '{value}' — erlaubt sind nur "
            "Kleinbuchstaben und Ziffern, kein Bindestrich (z.B. 'werkstatt')."
        )
    return value


def _validate_dateiname(dateiname: str) -> Path:
    """Validate a Zettel filename and return its full path in the mailbox.

    The name must match the Zettel scheme exactly (FILENAME_PATTERN). That
    rejects path separators, '..', drive letters, control characters (incl.
    embedded null bytes) and Windows device names (con, nul, …) in one step,
    since none of them fit the scheme — only real Zettel names are readable.
    """
    if not FILENAME_PATTERN.match(dateiname):
        raise BriefkastenError(
            f"Ungültiger Dateiname {dateiname!r} — erwartet wird ein "
            "Zettel-Name wie '2026-07-11_1430_werkstatt-an-architekt.md'."
        )
    folder = _briefkasten()
    path = folder / dateiname
    # Belt and suspenders: the resolved path must stay inside the mailbox.
    if path.resolve().parent != folder.resolve():
        raise BriefkastenError(
            f"Ungültiger Dateiname {dateiname!r} — Pfad verlässt den "
            "Briefkasten-Ordner."
        )
    return path


def _read_text(path: Path) -> str:
    """Read a Zettel file as UTF-8, translating failures into clear messages."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise BriefkastenError(
            f"Zettel '{path.name}' gibt es nicht — zettel_liste zeigt, "
            "was im Briefkasten liegt."
        )
    except UnicodeDecodeError:
        raise BriefkastenError(
            f"Zettel '{path.name}' ist nicht als UTF-8 lesbar — Datei "
            "vermutlich mit falschem Encoding gespeichert."
        )
    except OSError as exc:
        raise BriefkastenError(f"Zettel '{path.name}' nicht lesbar: {exc}")


def _parse_filename(dateiname: str) -> dict | None:
    """Split a Zettel filename into von, an, and its timestamp.

    Returns {von, an, zeitpunkt} when the name matches the Zettel scheme
    with a real timestamp, or None for anything else — a stray file, or a
    name that fits the pattern but whose time part is not a valid time.
    """
    match = FILENAME_PATTERN.match(dateiname)
    if not match:
        return None
    datum, uhrzeit, von, an, _suffix = match.groups()
    try:
        zeitpunkt = datetime.strptime(f"{datum}_{uhrzeit}", "%Y-%m-%d_%H%M")
    except ValueError:
        return None
    return {"von": von, "an": an, "zeitpunkt": zeitpunkt}


def _alter(zeitpunkt: datetime, jetzt: datetime) -> str:
    """Human-readable German age of a Zettel, relative to jetzt."""
    delta = jetzt - zeitpunkt
    sekunden = delta.total_seconds()
    if sekunden < 0:
        return "in der Zukunft"
    if sekunden < 60:
        return "gerade eben"
    if sekunden < 3600:
        n = int(sekunden // 60)
        return f"vor {n} Minute{'n' if n != 1 else ''}"
    if delta.days < 1:
        n = int(sekunden // 3600)
        return f"vor {n} Stunde{'n' if n != 1 else ''}"
    n = delta.days
    return f"vor {n} Tag{'en' if n != 1 else ''}"


@mcp.tool()
def zettel_liste(an: str | None = None) -> str:
    """List unread Zettel in the mailbox, newest first.

    Each line shows sender, recipient, timestamp, age, and the filename to
    hand to zettel_lesen. Pass 'an' to show only Zettel addressed to that
    room (e.g. an="architekt"); omit it to list all. Read Zettel live in the
    gelesen/ subfolder and are never listed.
    """
    if an is not None:
        an = _validate_name(an, "an")

    folder = _briefkasten()
    jetzt = datetime.now()

    try:
        zettel = []
        for path in folder.iterdir():
            if not path.is_file():
                continue
            parts = _parse_filename(path.name)
            if parts is None:
                continue
            if an is not None and parts["an"] != an:
                continue
            zettel.append((parts["zeitpunkt"], path.name, parts["von"], parts["an"]))
    except OSError as exc:
        raise BriefkastenError(
            f"Briefkasten-Ordner '{folder}' ist nicht lesbar: {exc}"
        )

    if not zettel:
        wen = f" für '{an}'" if an is not None else ""
        return f"Keine ungelesenen Zettel{wen}."

    zettel.sort(reverse=True)  # newest first
    lines = [
        f"{von} → {empf}   {zeit.strftime('%Y-%m-%d %H:%M')} "
        f"({_alter(zeit, jetzt)})   [{name}]"
        for zeit, name, von, empf in zettel
    ]
    return "\n".join(lines)


@mcp.tool()
def zettel_lesen(dateiname: str) -> str:
    """Return the full text of one Zettel from the mailbox.

    Pass the exact filename as shown by zettel_liste, e.g.
    "2026-07-11_1430_werkstatt-an-architekt.md". Rejects any filename that
    tries to leave the mailbox folder, and reports clearly when the Zettel
    does not exist.
    """
    path = _validate_dateiname(dateiname)
    return _read_text(path)


@mcp.tool()
def zettel_schreiben(von: str, an: str, inhalt: str) -> str:
    """Write a new Zettel to the mailbox and return its filename.

    'von' and 'an' are room names (lowercase letters/digits). 'inhalt' is
    the message body only — the "Von/An/Datum" header is added
    automatically. Never overwrites an existing Zettel: a name collision in
    the same minute gets a _2, _3, … suffix. Empty or whitespace-only
    inhalt is rejected.
    """
    von = _validate_name(von, "von")
    an = _validate_name(an, "an")
    if not inhalt or not inhalt.strip():
        raise BriefkastenError(
            "Der Zettel-Inhalt ist leer — bitte einen Text angeben."
        )

    folder = _briefkasten()
    jetzt = datetime.now()
    base = f"{jetzt.strftime('%Y-%m-%d_%H%M')}_{von}-an-{an}"
    kopf = f"Von: {von}\nAn: {an}\nDatum: {jetzt.strftime('%Y-%m-%d %H:%M')}\n\n"
    text = kopf + inhalt

    n = 1
    while True:
        name = f"{base}.md" if n == 1 else f"{base}_{n}.md"
        path = folder / name
        try:
            # "x": create-only — raises if the file already exists, so an
            # existing Zettel is never overwritten. newline="" keeps the
            # body's line endings exactly as written.
            with path.open("x", encoding="utf-8", newline="") as f:
                f.write(text)
            break
        except FileExistsError:
            # Same-minute collision — try the next suffix. Caught before the
            # OSError below on purpose: FileExistsError is a subclass of
            # OSError, so the generic handler would otherwise swallow the
            # retry path.
            n += 1
        except OSError as exc:
            raise BriefkastenError(
                f"Zettel '{name}' konnte nicht geschrieben werden: {exc}"
            )

    return name


if __name__ == "__main__":
    mcp.run()
